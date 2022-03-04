// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "../interfaces/uni/IUniswapV2Router02.sol";
import "../interfaces/uni/IUniswapV2Factory.sol";
import "../interfaces/uni/IUniswapV2Pair.sol";
import "../interfaces/IMasterChef.sol";
import "../interfaces/IERC20Extended.sol";

import "./ySwapper.sol";

import {UniswapV2Library} from "./libraries/UniswapV2Library.sol";

import {VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";

interface ProviderStrategy {
    function vault() external view returns (VaultAPI);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);

    function totalDebt() external view returns (uint256);
}

abstract contract Joint is ySwapper {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 internal constant RATIO_PRECISION = 1e4;

    ProviderStrategy public providerA;
    ProviderStrategy public providerB;

    address public tokenA;
    address public tokenB;

    address public WETH;
    address public reward;
    address public router;

    IUniswapV2Pair public pair;

    uint256 public investedA;
    uint256 public investedB;

    bool public dontInvestWant;
    bool public autoProtectionDisabled;

    uint256 public minAmountToSell;
    uint256 public maxPercentageLoss;
    uint256 public minRewardToHarvest;

    modifier onlyGovernance() {
        checkGovernance();
        _;
    }

    modifier onlyVaultManagers() {
        checkVaultManagers();
        _;
    }

    modifier onlyProviders() {
        checkProvider();
        _;
    }

    modifier onlyKeepers() {
        checkKeepers();
        _;
    }

    function checkKeepers() internal {
        require(isKeeper() || isGovernance() || isVaultManager());
    }

    function checkGovernance() internal {
        require(isGovernance());
    }

    function checkVaultManagers() internal {
        require(isGovernance() || isVaultManager());
    }

    function checkProvider() internal {
        require(isProvider());
    }

    function isGovernance() internal returns (bool) {
        return
            msg.sender == providerA.vault().governance() ||
            msg.sender == providerB.vault().governance();
    }

    function isVaultManager() internal returns (bool) {
        return
            msg.sender == providerA.vault().management() ||
            msg.sender == providerB.vault().management();
    }

    function isKeeper() internal returns (bool) {
        return
            (msg.sender == providerA.keeper()) ||
            (msg.sender == providerB.keeper());
    }

    function isProvider() internal returns (bool) {
        return
            msg.sender == address(providerA) ||
            msg.sender == address(providerB);
    }

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward
    ) public {
        _initialize(_providerA, _providerB, _router, _weth, _reward);
    }

    function _initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward
    ) internal virtual {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);
        router = _router;
        WETH = _weth;
        reward = _reward;

        tradeFactory = address(0xD3f89C21719Ec5961a3E6B0f9bBf9F9b4180E9e9);

        // NOTE: we let some loss to avoid getting locked in the position if something goes slightly wrong
        maxPercentageLoss = 10; // 0.10%

        tokenA = address(providerA.want());
        tokenB = address(providerB.want());
        require(tokenA != tokenB, "!same-want");
        pair = IUniswapV2Pair(getPair());

        IERC20(tokenA).approve(address(_router), type(uint256).max);
        IERC20(tokenB).approve(address(_router), type(uint256).max);
        IERC20(_reward).approve(address(_router), type(uint256).max);
        IERC20(address(pair)).approve(address(_router), type(uint256).max);
    }

    function name() external view virtual returns (string memory);

    function shouldEndEpoch() public view virtual returns (bool);

    function _autoProtect() internal view virtual returns (bool);

    function shouldStartEpoch() public view returns (bool) {
        // return true if we have balance of A or balance of B while the position is closed
        return
            (balanceOfA() > 0 || balanceOfB() > 0) &&
            investedA == 0 &&
            investedB == 0;
    }

    function setDontInvestWant(bool _dontInvestWant)
        external
        onlyVaultManagers
    {
        dontInvestWant = _dontInvestWant;
    }

    function setMinRewardToHarvest(uint256 _minRewardToHarvest)
        external
        onlyVaultManagers
    {
        minRewardToHarvest = _minRewardToHarvest;
    }

    function setMinAmountToSell(uint256 _minAmountToSell)
        external
        onlyVaultManagers
    {
        minAmountToSell = _minAmountToSell;
    }

    function setAutoProtectionDisabled(bool _autoProtectionDisabled)
        external
        onlyVaultManagers
    {
        autoProtectionDisabled = _autoProtectionDisabled;
    }

    function setMaxPercentageLoss(uint256 _maxPercentageLoss)
        external
        onlyVaultManagers
    {
        require(_maxPercentageLoss <= RATIO_PRECISION);
        maxPercentageLoss = _maxPercentageLoss;
    }

    function closePositionReturnFunds() external onlyProviders {
        // Check if it needs to stop starting new epochs after finishing this one. _autoProtect is implemented in children
        if (_autoProtect() && !autoProtectionDisabled) {
            dontInvestWant = true;
        }

        // Check that we have a position to close
        if (investedA == 0 || investedB == 0) {
            return;
        }

        // 1. CLOSE LIQUIDITY POSITION
        // Closing the position will:
        // - Remove liquidity from DEX
        // - Claim pending rewards
        // - Close Hedge and receive payoff
        // and returns current balance of tokenA and tokenB
        (uint256 currentBalanceA, uint256 currentBalanceB) = _closePosition();

        // 2. SELL REWARDS FOR WANT
        (address rewardSwappedTo, uint256 rewardSwapOutAmount) =
            swapReward(balanceOfReward());
        if (rewardSwappedTo == tokenA) {
            currentBalanceA = currentBalanceA.add(rewardSwapOutAmount);
        } else if (rewardSwappedTo == tokenB) {
            currentBalanceB = currentBalanceB.add(rewardSwapOutAmount);
        }

        // 3. REBALANCE PORTFOLIO
        // Calculate rebalance operation
        // It will return which of the tokens (A or B) we need to sell and how much of it to leave the position with the initial proportions
        (address sellToken, uint256 sellAmount) =
            calculateSellToBalance(
                currentBalanceA,
                currentBalanceB,
                investedA,
                investedB
            );

        if (sellToken != address(0) && sellAmount > minAmountToSell) {
            uint256 buyAmount =
                sellCapital(
                    sellToken,
                    sellToken == tokenA ? tokenB : tokenA,
                    sellAmount
                );
        }

        // reset invested balances
        investedA = investedB = 0;

        _returnLooseToProviders();
        // Check that we have returned with no losses
        //
        require(
            IERC20(tokenA).balanceOf(address(providerA)) >=
                providerA
                    .totalDebt()
                    .mul(RATIO_PRECISION.sub(maxPercentageLoss))
                    .div(RATIO_PRECISION),
            "!wrong-balanceA"
        );
        require(
            IERC20(tokenB).balanceOf(address(providerB)) >=
                providerB
                    .totalDebt()
                    .mul(RATIO_PRECISION.sub(maxPercentageLoss))
                    .div(RATIO_PRECISION),
            "!wrong-balanceB"
        );
    }

    function openPosition() external onlyProviders {
        // No capital, nothing to do
        if (balanceOfA() == 0 || balanceOfB() == 0) {
            return;
        }

        require(
            balanceOfStake() == 0 &&
                balanceOfPair() == 0 &&
                investedA == 0 &&
                investedB == 0
        ); // don't create LP if we are already invested

        (uint256 amountA, uint256 amountB, ) = createLP();
        (uint256 costHedgeA, uint256 costHedgeB) = hedgeLP();

        investedA = amountA.add(costHedgeA);
        investedB = amountB.add(costHedgeB);

        depositLP();

        if (tradesEnabled == false && tradeFactory != address(0)) {
            _setUpTradeFactory();
        }

        if (balanceOfStake() != 0 || balanceOfPair() != 0) {
            _returnLooseToProviders();
        }
    }

    function getYSwapTokens()
        internal
        view
        virtual
        override
        returns (address[] memory, address[] memory)
    {}

    function removeTradeFactoryPermissions()
        external
        virtual
        override
        onlyVaultManagers
    {}

    function updateTradeFactoryPermissions(address _newTradeFactory)
        external
        virtual
        override
        onlyGovernance
    {}

    // Keepers will claim and sell rewards mid-epoch (otherwise we sell only in the end)
    function harvest() external onlyKeepers {
        getReward();
    }

    function harvestTrigger() external view returns (bool) {
        return balanceOfReward() > minRewardToHarvest;
    }

    function getHedgeProfit() public view virtual returns (uint256, uint256);

    function estimatedTotalAssetsAfterBalance()
        public
        view
        virtual
        returns (uint256 _aBalance, uint256 _bBalance)
    {
        uint256 rewardsPending = pendingReward().add(balanceOfReward());

        (_aBalance, _bBalance) = balanceOfTokensInLP();

        _aBalance = _aBalance.add(balanceOfA());
        _bBalance = _bBalance.add(balanceOfB());

        (uint256 callProfit, uint256 putProfit) = getHedgeProfit();
        _aBalance = _aBalance.add(callProfit);
        _bBalance = _bBalance.add(putProfit);

        if (reward == tokenA) {
            _aBalance = _aBalance.add(rewardsPending);
        } else if (reward == tokenB) {
            _bBalance = _bBalance.add(rewardsPending);
        } else if (rewardsPending != 0) {
            address swapTo = findSwapTo(reward);
            uint256[] memory outAmounts =
                IUniswapV2Router02(router).getAmountsOut(
                    rewardsPending,
                    getTokenOutPath(reward, swapTo)
                );
            if (swapTo == tokenA) {
                _aBalance = _aBalance.add(outAmounts[outAmounts.length - 1]);
            } else if (swapTo == tokenB) {
                _bBalance = _bBalance.add(outAmounts[outAmounts.length - 1]);
            }
        }

        (address sellToken, uint256 sellAmount) =
            calculateSellToBalance(_aBalance, _bBalance, investedA, investedB);

        (uint256 reserveA, uint256 reserveB) = getReserves();

        if (sellToken == tokenA) {
            uint256 buyAmount =
                UniswapV2Library.getAmountOut(sellAmount, reserveA, reserveB);
            _aBalance = _aBalance.sub(sellAmount);
            _bBalance = _bBalance.add(buyAmount);
        } else if (sellToken == tokenB) {
            uint256 buyAmount =
                UniswapV2Library.getAmountOut(sellAmount, reserveB, reserveA);
            _bBalance = _bBalance.sub(sellAmount);
            _aBalance = _aBalance.add(buyAmount);
        }
    }

    function estimatedTotalAssetsInToken(address token)
        public
        view
        returns (uint256 _balance)
    {
        if (token == tokenA) {
            (_balance, ) = estimatedTotalAssetsAfterBalance();
        } else if (token == tokenB) {
            (, _balance) = estimatedTotalAssetsAfterBalance();
        }
    }

    function getHedgeBudget(address token)
        public
        view
        virtual
        returns (uint256);

    function hedgeLP() internal virtual returns (uint256, uint256);

    function closeHedge() internal virtual;

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view virtual returns (address _sellToken, uint256 _sellAmount) {
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        (uint256 ratioA, uint256 ratioB) =
            getRatios(currentA, currentB, startingA, startingB);

        if (ratioA == ratioB) return (address(0), 0);

        (uint256 reserveA, uint256 reserveB) = getReserves();

        if (ratioA > ratioB) {
            _sellToken = tokenA;
            _sellAmount = _calculateSellToBalance(
                currentA,
                currentB,
                startingA,
                startingB,
                reserveA,
                reserveB,
                10**uint256(IERC20Extended(tokenA).decimals())
            );
        } else {
            _sellToken = tokenB;
            _sellAmount = _calculateSellToBalance(
                currentB,
                currentA,
                startingB,
                startingA,
                reserveB,
                reserveA,
                10**uint256(IERC20Extended(tokenB).decimals())
            );
        }
    }

    function _calculateSellToBalance(
        uint256 current0,
        uint256 current1,
        uint256 starting0,
        uint256 starting1,
        uint256 reserve0,
        uint256 reserve1,
        uint256 precision
    ) internal pure returns (uint256 _sellAmount) {
        uint256 numerator =
            current0.sub(starting0.mul(current1).div(starting1)).mul(precision);
        uint256 denominator;
        uint256 exchangeRate;

        // First time to approximate
        exchangeRate = UniswapV2Library.getAmountOut(
            precision,
            reserve0,
            reserve1
        );
        denominator = precision + starting0.mul(exchangeRate).div(starting1);
        _sellAmount = numerator.div(denominator);
        // Shortcut to avoid Uniswap amountIn == 0 revert
        if (_sellAmount == 0) {
            return 0;
        }

        // Second time to account for price impact
        exchangeRate = UniswapV2Library
            .getAmountOut(_sellAmount, reserve0, reserve1)
            .mul(precision)
            .div(_sellAmount);
        denominator = precision + starting0.mul(exchangeRate).div(starting1);
        _sellAmount = numerator.div(denominator);
    }

    function getRatios(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal pure returns (uint256 _a, uint256 _b) {
        _a = currentA.mul(RATIO_PRECISION).div(startingA);
        _b = currentB.mul(RATIO_PRECISION).div(startingB);
    }

    function getReserves()
        public
        view
        returns (uint256 reserveA, uint256 reserveB)
    {
        if (tokenA == pair.token0()) {
            (reserveA, reserveB, ) = pair.getReserves();
        } else {
            (reserveB, reserveA, ) = pair.getReserves();
        }
    }

    function createLP()
        internal
        virtual
        returns (
            uint256,
            uint256,
            uint256
        )
    {
        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        return
            IUniswapV2Router02(router).addLiquidity(
                tokenA,
                tokenB,
                balanceOfA()
                    .mul(RATIO_PRECISION.sub(getHedgeBudget(tokenA)))
                    .div(RATIO_PRECISION),
                balanceOfB()
                    .mul(RATIO_PRECISION.sub(getHedgeBudget(tokenB)))
                    .div(RATIO_PRECISION),
                0,
                0,
                address(this),
                now
            );
    }

    function findSwapTo(address token) internal view returns (address) {
        if (tokenA == token) {
            return tokenB;
        } else if (tokenB == token) {
            return tokenA;
        } else if (reward == token) {
            if (tokenA == WETH || tokenB == WETH) {
                return WETH;
            }
            return tokenA;
        } else {
            revert("!swapTo");
        }
    }

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        bool is_weth =
            _token_in == address(WETH) || _token_out == address(WETH);
        bool is_internal =
            (_token_in == tokenA && _token_out == tokenB) ||
                (_token_in == tokenB && _token_out == tokenA);
        _path = new address[](is_weth || is_internal ? 2 : 3);
        _path[0] = _token_in;
        if (is_weth || is_internal) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(WETH);
            _path[2] = _token_out;
        }
    }

    function getReward() internal virtual;

    function depositLP() internal virtual;

    function withdrawLP() internal virtual;

    function swapReward(uint256 _rewardBal)
        internal
        virtual
        returns (address, uint256)
    {
        if (reward == tokenA || reward == tokenB || _rewardBal == 0) {
            return (reward, 0);
        }

        if (tokenA == WETH || tokenB == WETH) {
            return (WETH, sellCapital(reward, WETH, _rewardBal));
        }

        // Assume that position has already been liquidated
        (uint256 ratioA, uint256 ratioB) =
            getRatios(balanceOfA(), balanceOfB(), investedA, investedB);
        if (ratioA >= ratioB) {
            return (tokenB, sellCapital(reward, tokenB, _rewardBal));
        }
        return (tokenA, sellCapital(reward, tokenA, _rewardBal));
    }

    // If there is a lot of impermanent loss, some capital will need to be sold
    // To make both sides even
    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal virtual returns (uint256 _amountOut) {
        uint256[] memory amounts =
            IUniswapV2Router02(router).swapExactTokensForTokens(
                _amountIn,
                0,
                getTokenOutPath(_tokenFrom, _tokenTo),
                address(this),
                now
            );
        _amountOut = amounts[amounts.length - 1];
    }

    function _closePosition() internal virtual returns (uint256, uint256) {
        // Unstake LP from staking contract
        withdrawLP();

        // Close the hedge
        closeHedge();

        if (balanceOfPair() == 0) {
            return (0, 0);
        }

        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        IUniswapV2Router02(router).removeLiquidity(
            tokenA,
            tokenB,
            balanceOfPair(),
            0,
            0,
            address(this),
            now
        );

        return (balanceOfA(), balanceOfB());
    }

    function _returnLooseToProviders()
        internal
        returns (uint256 balanceA, uint256 balanceB)
    {
        balanceA = balanceOfA();
        if (balanceA > 0) {
            IERC20(tokenA).safeTransfer(address(providerA), balanceA);
        }

        balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).safeTransfer(address(providerB), balanceB);
        }
    }

    function getPair() internal view virtual returns (address) {
        address factory = IUniswapV2Router02(router).factory();
        return IUniswapV2Factory(factory).getPair(tokenA, tokenB);
    }

    function balanceOfPair() public view returns (uint256) {
        return IERC20(getPair()).balanceOf(address(this));
    }

    function balanceOfA() public view returns (uint256) {
        return IERC20(tokenA).balanceOf(address(this));
    }

    function balanceOfB() public view returns (uint256) {
        return IERC20(tokenB).balanceOf(address(this));
    }

    function balanceOfReward() public view returns (uint256) {
        return IERC20(reward).balanceOf(address(this));
    }

    function balanceOfStake() public view virtual returns (uint256);

    function balanceOfTokensInLP()
        public
        view
        returns (uint256 _balanceA, uint256 _balanceB)
    {
        (uint256 reserveA, uint256 reserveB) = getReserves();
        uint256 lpBal = balanceOfStake().add(balanceOfPair());
        uint256 pairPrecision = 10**uint256(pair.decimals());
        uint256 percentTotal = lpBal.mul(pairPrecision).div(pair.totalSupply());
        _balanceA = reserveA.mul(percentTotal).div(pairPrecision);
        _balanceB = reserveB.mul(percentTotal).div(pairPrecision);
    }

    function pendingReward() public view virtual returns (uint256);

    // --- MANAGEMENT FUNCTIONS ---
    function liquidatePositionManually(
        uint256 expectedBalanceA,
        uint256 expectedBalanceB
    ) external onlyVaultManagers {
        (uint256 balanceA, uint256 balanceB) = _closePosition();
        require(expectedBalanceA <= balanceA, "!sandwidched");
        require(expectedBalanceB <= balanceB, "!sandwidched");
    }

    function returnLooseToProvidersManually() external onlyVaultManagers {
        _returnLooseToProviders();
    }

    function removeLiquidityManually(
        uint256 amount,
        uint256 expectedBalanceA,
        uint256 expectedBalanceB
    ) external virtual onlyVaultManagers {
        IUniswapV2Router02(router).removeLiquidity(
            tokenA,
            tokenB,
            amount,
            0,
            0,
            address(this),
            now
        );
        require(expectedBalanceA <= balanceOfA(), "!sandwidched");
        require(expectedBalanceB <= balanceOfB(), "!sandwidched");
    }

    function swapTokenForTokenManually(
        address[] memory swapPath,
        uint256 swapInAmount,
        uint256 minOutAmount
    ) external onlyGovernance returns (uint256) {
        address swapTo = swapPath[swapPath.length - 1];
        require(swapTo == tokenA || swapTo == tokenB); // swapTo must be tokenA or tokenB
        uint256[] memory amounts =
            IUniswapV2Router02(router).swapExactTokensForTokens(
                swapInAmount,
                minOutAmount,
                swapPath,
                address(this),
                now
            );
        return amounts[amounts.length - 1];
    }

    function sweep(address _token) external onlyGovernance {
        require(_token != address(tokenA));
        require(_token != address(tokenB));

        SafeERC20.safeTransfer(
            IERC20(_token),
            providerA.vault().governance(),
            IERC20(_token).balanceOf(address(this))
        );
    }

    function migrateProvider(address _newProvider) external onlyProviders {
        ProviderStrategy newProvider = ProviderStrategy(_newProvider);
        if (address(newProvider.want()) == tokenA) {
            providerA = newProvider;
        } else if (address(newProvider.want()) == tokenB) {
            providerB = newProvider;
        } else {
            revert("Unsupported token");
        }
    }
}
