// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

import "../interfaces/IERC20Extended.sol";

import "./ySwapper.sol";

import {VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";

interface ProviderStrategy {
    function vault() external view returns (VaultAPI);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);

    function totalDebt() external view returns (uint256);
}

abstract contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;

    uint256 internal constant RATIO_PRECISION = 1e18;

    ProviderStrategy public providerA;
    ProviderStrategy public providerB;

    address public tokenA;
    address public tokenB;

    address public WETH;
    address[] public rewardTokens;

    address public pool;

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

    function isGovernance() internal view returns (bool) {
        return
            msg.sender == providerA.vault().governance() ||
            msg.sender == providerB.vault().governance();
    }

    function isVaultManager() internal view returns (bool) {
        return
            msg.sender == providerA.vault().management() ||
            msg.sender == providerB.vault().management();
    }

    function isKeeper() internal view returns (bool) {
        return
            (msg.sender == providerA.keeper()) ||
            (msg.sender == providerB.keeper());
    }

    function isProvider() internal view returns (bool) {
        return
            msg.sender == address(providerA) ||
            msg.sender == address(providerB);
    }

    constructor(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool
    ) {
        _initialize(_providerA, _providerB, _weth, _pool);
    }

    function _initialize(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool
    ) internal virtual {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);
        WETH = _weth;
        pool = _pool;

        // NOTE: we let some loss to avoid getting locked in the position if something goes slightly wrong
        maxPercentageLoss = RATIO_PRECISION / 1_000; // 0.10%

        tokenA = address(providerA.want());
        tokenB = address(providerB.want());
        require(tokenA != tokenB, "!same-want");
    }

    function name() external view virtual returns (string memory);

    function shouldEndEpoch() external view virtual returns (bool);

    function _autoProtect() internal view virtual returns (bool);

    function _isReward(address token) internal view returns (bool) {
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            if (rewardTokens[i] == token) {
                return true;
            }
        }

        return false;
    }

    function shouldStartEpoch() external view returns (bool) {
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
        tokenAmount[] memory swappedToAmounts = swapRewardTokens();
        for (uint256 i = 0; i < swappedToAmounts.length; i++) {
            address rewardSwappedTo = swappedToAmounts[i].token;
            uint256 rewardSwapOutAmount = swappedToAmounts[i].amount;
            if (rewardSwappedTo == tokenA) {
                currentBalanceA = currentBalanceA + rewardSwapOutAmount;
            } else if (rewardSwappedTo == tokenB) {
                currentBalanceB = currentBalanceB + rewardSwapOutAmount;
            }
        }

        // 3. REBALANCE PORTFOLIO
        // Calculate rebalance operation
        // It will return which of the tokens (A or B) we need to sell and how much of it to leave the position with the initial proportions
        (address sellToken, uint256 sellAmount) = calculateSellToBalance(
            currentBalanceA,
            currentBalanceB,
            investedA,
            investedB
        );

        if (sellToken != address(0) && sellAmount > minAmountToSell) {
            uint256 buyAmount = swap(
                sellToken,
                sellToken == tokenA ? tokenB : tokenA,
                sellAmount
            );
        }

        // reset invested balances
        investedA = investedB = 0;

        _returnLooseToProviders();
        // Check that we have returned with no losses

        require(
            IERC20(tokenA).balanceOf(address(providerA)) >=
                (providerA.totalDebt() *
                    (RATIO_PRECISION - maxPercentageLoss)) /
                    RATIO_PRECISION,
            "!wrong-balanceA"
        );
        require(
            IERC20(tokenB).balanceOf(address(providerB)) >=
                (providerB.totalDebt() *
                    (RATIO_PRECISION - maxPercentageLoss)) /
                    RATIO_PRECISION,
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
                balanceOfPool() == 0 &&
                investedA == 0 &&
                investedB == 0
        ); // don't create LP if we are already invested

        (uint256 amountA, uint256 amountB) = createLP();
        (uint256 costHedgeA, uint256 costHedgeB) = hedgeLP();

        investedA = amountA + costHedgeA;
        investedB = amountB + costHedgeB;

        depositLP();

        if (balanceOfStake() != 0 || balanceOfPool() != 0) {
            _returnLooseToProviders();
        }
    }

    // Keepers will claim and sell rewards mid-epoch (otherwise we sell only in the end)
    function harvest() external onlyKeepers {
        getReward();
    }

    function harvestTrigger() external view returns (bool) {
        return balanceOfRewardToken()[0] > minRewardToHarvest;
    }

    function getHedgeProfit() public view virtual returns (uint256, uint256);

    function estimatedTotalAssetsAfterBalance()
        public
        view
        returns (uint256 _aBalance, uint256 _bBalance)
    {
        (_aBalance, _bBalance) = balanceOfTokensInLP();

        _aBalance = _aBalance + balanceOfA();
        _bBalance = _bBalance + balanceOfB();

        (uint256 callProfit, uint256 putProfit) = getHedgeProfit();
        _aBalance = _aBalance + callProfit;
        _bBalance = _bBalance + putProfit;

        uint256[] memory _rewardsPending = pendingRewards();
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            address reward = rewardTokens[i];
            if (reward == tokenA) {
                _aBalance = _aBalance + _rewardsPending[i];
            } else if (reward == tokenB) {
                _bBalance = _bBalance + _rewardsPending[i];
            } else if (_rewardsPending[i] != 0) {
                address swapTo = findSwapTo(reward);
                uint256 outAmount = quote(
                    reward,
                    swapTo,
                    _rewardsPending[i] + IERC20(reward).balanceOf(address(this))
                );
                if (swapTo == tokenA) {
                    _aBalance = _aBalance + outAmount;
                } else if (swapTo == tokenB) {
                    _bBalance = _bBalance + outAmount;
                }
            }
        }

        (address sellToken, uint256 sellAmount) = calculateSellToBalance(
            _aBalance,
            _bBalance,
            investedA,
            investedB
        );

        if (sellToken == tokenA) {
            uint256 buyAmount = quote(sellToken, tokenB, sellAmount);
            _aBalance = _aBalance - sellAmount;
            _bBalance = _bBalance + buyAmount;
        } else if (sellToken == tokenB) {
            uint256 buyAmount = quote(sellToken, tokenA, sellAmount);
            _bBalance = _bBalance - sellAmount;
            _aBalance = _aBalance + buyAmount;
        }
    }

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view returns (address _sellToken, uint256 _sellAmount) {
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        (uint256 ratioA, uint256 ratioB) = getRatios(
            currentA,
            currentB,
            startingA,
            startingB
        );

        if (ratioA == ratioB) return (address(0), 0);

        if (ratioA > ratioB) {
            _sellToken = tokenA;
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentA,
                currentB,
                startingA,
                startingB,
                10**uint256(IERC20Extended(tokenA).decimals())
            );
        } else {
            _sellToken = tokenB;
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentB,
                currentA,
                startingB,
                startingA,
                10**uint256(IERC20Extended(tokenB).decimals())
            );
        }
    }

    function _calculateSellToBalance(
        address sellToken,
        uint256 current0,
        uint256 current1,
        uint256 starting0,
        uint256 starting1,
        uint256 precision
    ) internal view returns (uint256 _sellAmount) {
        uint256 numerator = (current0 - ((starting0 * current1) / starting1)) *
            precision;
        uint256 exchangeRate = quote(
            sellToken,
            sellToken == tokenA ? tokenB : tokenA,
            precision
        );

        // First time to approximate
        _sellAmount =
            numerator /
            (precision + ((starting0 * exchangeRate) / starting1));
        // Shortcut to avoid Uniswap amountIn == 0 revert
        if (_sellAmount == 0) {
            return 0;
        }

        // Second time to account for price impact
        exchangeRate =
            (quote(
                sellToken,
                sellToken == tokenA ? tokenB : tokenA,
                _sellAmount
            ) * precision) /
            _sellAmount;
        _sellAmount =
            numerator /
            (precision + ((starting0 * exchangeRate) / starting1));
    }

    function estimatedTotalProviderAssets(address _provider)
        public
        view
        returns (uint256 _balance)
    {
        if (_provider == address(providerA)) {
            (_balance, ) = estimatedTotalAssetsAfterBalance();
        } else if (_provider == address(providerB)) {
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

    function getRatios(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) public pure returns (uint256 _a, uint256 _b) {
        _a = (currentA * RATIO_PRECISION) / startingA;
        _b = (currentB * RATIO_PRECISION) / startingB;
    }

    function createLP() internal virtual returns (uint256, uint256);

    function burnLP(uint256 amount) internal virtual;

    function findSwapTo(address token) internal view returns (address) {
        if (tokenA == token) {
            return tokenB;
        } else if (tokenB == token) {
            return tokenA;
        } else if (_isReward(token)) {
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
        bool is_weth = _token_in == address(WETH) ||
            _token_out == address(WETH);
        bool is_internal = (_token_in == tokenA && _token_out == tokenB) ||
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

    function depositLP() internal virtual {}

    function withdrawLP() internal virtual {}

    struct tokenAmount {
        address token;
        uint256 amount;
    }

    function swapRewardTokens()
        internal
        virtual
        returns (tokenAmount[] memory)
    {
        tokenAmount[] memory _swapToAmounts = new tokenAmount[](
            rewardTokens.length
        );
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            address reward = rewardTokens[i];
            uint256 _rewardBal = IERC20(reward).balanceOf(address(this));
            if (reward == tokenA || reward == tokenB || _rewardBal == 0) {
                _swapToAmounts[i] = tokenAmount(reward, 0);
            } else if (tokenA == WETH || tokenB == WETH) {
                _swapToAmounts[i] = tokenAmount(
                    WETH,
                    swap(reward, WETH, _rewardBal)
                );
            } else {
                // Assume that position has already been liquidated
                (uint256 ratioA, uint256 ratioB) = getRatios(
                    balanceOfA(),
                    balanceOfB(),
                    investedA,
                    investedB
                );
                address swapTo = (ratioA >= ratioB) ? tokenB : tokenA;
                _swapToAmounts[i] = tokenAmount(
                    swapTo,
                    swap(reward, swapTo, _rewardBal)
                );
            }
        }
        return _swapToAmounts;
    }

    function swap(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal virtual returns (uint256 _amountOut);

    function quote(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal view virtual returns (uint256 _amountOut);

    function _closePosition() internal returns (uint256, uint256) {
        // Unstake LP from staking contract
        withdrawLP();

        // Close the hedge
        closeHedge();

        if (balanceOfPool() == 0) {
            return (0, 0);
        }

        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        burnLP(balanceOfPool());

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

    function balanceOfA() public view returns (uint256) {
        return IERC20(tokenA).balanceOf(address(this));
    }

    function balanceOfB() public view returns (uint256) {
        return IERC20(tokenB).balanceOf(address(this));
    }

    function balanceOfPool() public view virtual returns (uint256);

    function balanceOfRewardToken() public view returns (uint256[] memory) {
        uint256[] memory _balances = new uint256[](rewardTokens.length);
        for (uint8 i = 0; i < rewardTokens.length; i++) {
            _balances[i] = IERC20(rewardTokens[i]).balanceOf(address(this));
        }
        return _balances;
    }

    function balanceOfStake() public view virtual returns (uint256 _balance) {}

    function balanceOfTokensInLP()
        public
        view
        virtual
        returns (uint256 _balanceA, uint256 _balanceB);

    function pendingRewards() public view virtual returns (uint256[] memory);

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
        burnLP(amount);
        require(expectedBalanceA <= balanceOfA(), "!sandwidched");
        require(expectedBalanceB <= balanceOfB(), "!sandwidched");
    }

    function swapTokenForTokenManually(
        address[] memory swapPath,
        uint256 swapInAmount,
        uint256 minOutAmount
    ) external onlyGovernance returns (uint256) {}

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
