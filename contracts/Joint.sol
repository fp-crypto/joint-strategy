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
import "./LPHedgingLib.sol";
import "../interfaces/uni/IUniswapV2Router02.sol";
import "../interfaces/uni/IUniswapV2Factory.sol";
import "../interfaces/uni/IUniswapV2Pair.sol";
import "../interfaces/IMasterChef.sol";

import {UniswapV2Library} from "./libraries/UniswapV2Library.sol";

import {VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";

interface ProviderStrategy {
    function vault() external view returns (VaultAPI);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);
}

abstract contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 private constant RATIO_PRECISION = 1e4;

    ProviderStrategy public providerA;
    ProviderStrategy public providerB;

    address public tokenA;
    address public tokenB;

    address public WETH;
    address public reward;
    address public router;

    uint256 public pid;

    IMasterchef public masterchef;

    IUniswapV2Pair public pair;

    uint256 private investedA;
    uint256 private investedB;

    // HEDGING
    bool public isHedgingDisabled;

    uint256 public activeCallID;
    uint256 public activePutID;

    uint256 public hedgeBudget = 50; // 0.5% per hedging period
    uint256 private protectionRange = 1000; // 10%
    uint256 private period = 1 days;

    modifier onlyGovernance {
        require(
            msg.sender == providerA.vault().governance() ||
                msg.sender == providerB.vault().governance()
        );
        _;
    }

    modifier onlyAuthorized {
        require(
            msg.sender == providerA.vault().governance() ||
                msg.sender == providerB.vault().governance() ||
                msg.sender == providerA.strategist() ||
                msg.sender == providerB.strategist()
        );
        _;
    }

    modifier onlyProviders {
        require(
            msg.sender == address(providerA) || msg.sender == address(providerB)
        );
        _;
    }

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) public {
        _initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        );
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) external {
        _initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        );
    }

    function _initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) internal {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);
        router = _router;
        WETH = _weth;
        masterchef = IMasterchef(_masterchef);
        reward = _reward;
        pid = _pid;

        tokenA = address(providerA.want());
        tokenB = address(providerB.want());

        pair = IUniswapV2Pair(getPair());

        IERC20(address(pair)).approve(address(masterchef), type(uint256).max);
        IERC20(tokenA).approve(address(router), type(uint256).max);
        IERC20(tokenB).approve(address(router), type(uint256).max);
        IERC20(reward).approve(address(router), type(uint256).max);
        IERC20(address(pair)).approve(address(router), type(uint256).max);

        period = 1 days;
        protectionRange = 1_000;
        hedgeBudget = 50;
    }

    event Cloned(address indexed clone);

    function cloneJoint(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    ) external returns (address newJoint) {
        bytes20 addressBytes = bytes20(address(this));

        assembly {
            // EIP-1167 bytecode
            let clone_code := mload(0x40)
            mstore(
                clone_code,
                0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000
            )
            mstore(add(clone_code, 0x14), addressBytes)
            mstore(
                add(clone_code, 0x28),
                0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000
            )
            newJoint := create(0, clone_code, 0x37)
        }

        Joint(newJoint).initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        );

        emit Cloned(newJoint);
    }

    function name() external view virtual returns (string memory) {}

    function prepareReturn(bool returnFunds) external onlyProviders {
        // If we have previously invested funds, let's distribute PnL equally in
        // each token's own terms
        if (investedA != 0 && investedB != 0) {
            // Liquidate will also claim rewards & close hedge
            (uint256 currentA, uint256 currentB) = _liquidatePosition();

            if (tokenA != reward && tokenB != reward) {
                (address rewardSwappedTo, uint256 rewardSwapOutAmount) =
                    swapReward(balanceOfReward());
                if (rewardSwappedTo == tokenA) {
                    currentA = currentA.add(rewardSwapOutAmount);
                } else if (rewardSwappedTo == tokenB) {
                    currentB = currentB.add(rewardSwapOutAmount);
                }
            }

            (address sellToken, uint256 sellAmount) =
                calculateSellToBalance(
                    currentA,
                    currentB,
                    investedA,
                    investedB
                );

            if (sellToken != address(0) && sellAmount != 0) {
                uint256 buyAmount =
                    sellCapital(
                        sellToken,
                        sellToken == tokenA ? tokenB : tokenA,
                        sellAmount
                    );

                if (sellToken == tokenA) {
                    currentA = currentA.sub(sellAmount);
                    currentB = currentB.add(buyAmount);
                } else {
                    currentB = currentB.sub(sellAmount);
                    currentA = currentA.add(buyAmount);
                }
            }
        }

        investedA = investedB = 0;

        if (returnFunds) {
            _returnLooseToProviders();
        }
    }

    function adjustPosition() external onlyProviders {
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

        (investedA, investedB, ) = createLP();
        if (hedgeBudget > 0 && !isHedgingDisabled) {
            // take into account that if hedgeBudget is not enough, it will revert
            (uint256 costCall, uint256 costPut) = hedgeLP();
            investedA += costCall;
            investedB += costPut;
        }
        depositLP();

        if (balanceOfStake() != 0 || balanceOfPair() != 0) {
            _returnLooseToProviders();
        }
    }

    function getOptionsProfit() public view returns (uint256, uint256) {
        return LPHedgingLib.getOptionsProfit(activeCallID, activePutID);
    }

    function estimatedTotalAssetsAfterBalance()
        public
        view
        returns (uint256 _aBalance, uint256 _bBalance)
    {
        uint256 rewardsPending = pendingReward();

        (_aBalance, _bBalance) = balanceOfTokensInLP();

        _aBalance = _aBalance.add(balanceOfA());
        _bBalance = _bBalance.add(balanceOfB());

        (uint256 callProfit, uint256 putProfit) = getOptionsProfit();
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
        external
        view
        returns (uint256 _balance)
    {
        if (token == tokenA) {
            (_balance, ) = estimatedTotalAssetsAfterBalance();
        } else if (token == tokenB) {
            (, _balance) = estimatedTotalAssetsAfterBalance();
        }
    }

    function hedgeLP() internal returns (uint256, uint256) {
        IERC20 _pair = IERC20(getPair());
        uint256 initialBalanceA = balanceOfA();
        uint256 initialBalanceB = balanceOfB();
        require(activeCallID == 0 && activePutID == 0);
        (activeCallID, activePutID) = LPHedgingLib.hedgeLPToken(
            address(_pair),
            protectionRange,
            period
        );
        uint256 costCall = initialBalanceA.sub(balanceOfA());
        uint256 costPut = initialBalanceB.sub(balanceOfB());
        return (costCall, costPut);
    }

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view returns (address _sellToken, uint256 _sellAmount) {
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
                balanceOfA().mul(RATIO_PRECISION.sub(hedgeBudget)).div(
                    RATIO_PRECISION
                ),
                balanceOfB().mul(RATIO_PRECISION.sub(hedgeBudget)).div(
                    RATIO_PRECISION
                ),
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

    function getReward() internal {
        masterchef.deposit(pid, 0);
    }

    function depositLP() internal {
        if (balanceOfPair() > 0) masterchef.deposit(pid, balanceOfPair());
    }

    function swapReward(uint256 _rewardBal)
        internal
        returns (address _swapTo, uint256 _receivedAmount)
    {
        if (reward == tokenA || reward == tokenB || _rewardBal == 0) {
            return (address(0), 0);
        }

        _swapTo = findSwapTo(reward);
        _receivedAmount = sellCapital(reward, _swapTo, _rewardBal);
    }

    // If there is a lot of impermanent loss, some capital will need to be sold
    // To make both sides even
    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal returns (uint256 _amountOut) {
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

    function _liquidatePosition() internal returns (uint256, uint256) {
        if (balanceOfStake() != 0) {
            masterchef.withdraw(pid, balanceOfStake());
        }

        if (balanceOfPair() == 0) {
            return (0, 0);
        }
        // only close hedge if a hedge is open
        if (activeCallID != 0 && activePutID != 0 && !isHedgingDisabled) {
            LPHedgingLib.closeHedge(activeCallID, activePutID);
        }

        activeCallID = 0;
        activePutID = 0;
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

    function _returnLooseToProviders() internal {
        uint256 balanceA = balanceOfA();
        if (balanceA > 0) {
            IERC20(tokenA).transfer(address(providerA), balanceA);
        }

        uint256 balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).transfer(address(providerB), balanceB);
        }
    }

    function onERC721Received(
        address,
        address,
        uint256,
        bytes calldata
    ) public pure virtual returns (bytes4) {
        return this.onERC721Received.selector;
    }

    function getPair() internal view returns (address) {
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

    function balanceOfStake() public view returns (uint256) {
        return masterchef.userInfo(pid, address(this)).amount;
    }

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

    function pendingReward() public view virtual returns (uint256) {}

    function liquidatePosition() external onlyAuthorized {
        _liquidatePosition();
    }

    function returnLooseToProviders() external onlyAuthorized {
        _returnLooseToProviders();
    }

    function setIsHedgingDisabled(bool _isHedgingDisabled, bool force)
        external
        onlyAuthorized
    {
        // if there is an active hedge, we need to force the disabling
        if (force || (activeCallID == 0 && activePutID == 0)) {
            isHedgingDisabled = _isHedgingDisabled;
        }
    }

    function setHedgeBudget(uint256 _hedgeBudget) external onlyAuthorized {
        require(_hedgeBudget < RATIO_PRECISION);
        hedgeBudget = _hedgeBudget;
    }

    function setHedgingPeriod(uint256 _period) external onlyAuthorized {
        require(_period < 90 days);
        period = _period;
    }

    function setProtectionRange(uint256 _protectionRange)
        external
        onlyAuthorized
    {
        require(_protectionRange < RATIO_PRECISION);
        protectionRange = _protectionRange;
    }

    function withdrawFromMasterchef() external onlyAuthorized {
        masterchef.withdraw(pid, balanceOfStake());
    }

    function removeLiquidity(uint256 amount) external onlyAuthorized {
        IUniswapV2Router02(router).removeLiquidity(
            tokenA,
            tokenB,
            balanceOfPair(),
            0,
            0,
            address(this),
            now
        );
    }

    function resetHedge() external onlyGovernance {
        activeCallID = 0;
        activePutID = 0;
    }

    function swapTokenForToken(address[] memory swapPath, uint256 swapInAmount)
        external
        onlyGovernance
        returns (uint256)
    {
        address swapTo = swapPath[swapPath.length - 1];
        require(swapTo == tokenA || swapTo == tokenB); // swapTo must be tokenA or tokenB
        uint256[] memory amounts =
            IUniswapV2Router02(router).swapExactTokensForTokens(
                swapInAmount,
                0,
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
}
