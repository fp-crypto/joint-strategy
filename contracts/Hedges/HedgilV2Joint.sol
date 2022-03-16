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
import "../Joint.sol";

interface IHedgilPool {
    function quoteToken() external view returns (address);

    function getTimeToMaturity(uint256 hedgeID) external view returns (uint256);

    function getCurrentPayout(uint256 hedgeID) external view returns (uint256);

    function hedgeLPToken(
        address pair,
        uint256 protectionRange,
        uint256 period
    ) external returns (uint256, uint256);

    function closeHedge(uint256 hedgedID)
        external
        returns (uint256 payoff, uint256 exercisePrice);
}

abstract contract HedgilV2Joint is Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 public activeHedgeID;

    uint256 public hedgeBudget;
    uint256 public protectionRange;
    uint256 public period;

    uint256 private minTimeToMaturity;

    bool public skipManipulatedCheck;
    bool public isHedgingEnabled;

    uint256 public maxSlippageOpen;
    uint256 public maxSlippageClose;

    address public hedgilPool;

    uint256 private constant PRICE_DECIMALS = 1e18;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _hedgilPool
    ) public Joint(_providerA, _providerB, _router, _weth, _reward) {
        _initializeHedgilJoint(_hedgilPool);
    }

    function _initializeHedgilJoint(address _hedgilPool) internal {
        hedgilPool = _hedgilPool;
        require(IHedgilPool(_hedgilPool).quoteToken() == tokenB); // dev: tokenB != quotetoken

        hedgeBudget = 25; // 0.25% per hedging period
        protectionRange = 1000; // 10%
        period = 7 days;
        minTimeToMaturity = 3600; // 1 hour
        maxSlippageOpen = 100; // 1%
        maxSlippageClose = 100; // 1%

        isHedgingEnabled = true;

        IERC20(tokenB).approve(_hedgilPool, type(uint256).max);
    }

    function getHedgeBudget(address token)
        public
        view
        override
        returns (uint256)
    {
        // Hedgil only accepts the quote token
        if (token == address(tokenB)) {
            return hedgeBudget;
        }

        return 0;
    }

    function getTimeToMaturity() public view returns (uint256) {
        return IHedgilPool(hedgilPool).getTimeToMaturity(activeHedgeID);
    }

    function getHedgeProfit() public view override returns (uint256, uint256) {
        // Handle the case where hedgil is closed but estimatedTotalAssets is called in any of the
        // Provider strats (happens when closing epoch and vault.report calls estimatedTotalAssets)
        if (activeHedgeID == 0) {
            return (0, 0);
        }
        return (0, IHedgilPool(hedgilPool).getCurrentPayout(activeHedgeID));
    }

    function setSkipManipulatedCheck(bool _skipManipulatedCheck)
        external
        onlyVaultManagers
    {
        skipManipulatedCheck = _skipManipulatedCheck;
    }

    function setMaxSlippageClose(uint256 _maxSlippageClose)
        external
        onlyVaultManagers
    {
        require(_maxSlippageClose <= RATIO_PRECISION); // dev: !boundary
        maxSlippageClose = _maxSlippageClose;
    }

    function setMaxSlippageOpen(uint256 _maxSlippageOpen)
        external
        onlyVaultManagers
    {
        require(_maxSlippageOpen <= RATIO_PRECISION); // dev: !boundary
        maxSlippageOpen = _maxSlippageOpen;
    }

    function setMinTimeToMaturity(uint256 _minTimeToMaturity)
        external
        onlyVaultManagers
    {
        require(_minTimeToMaturity <= period); // avoid incorrect settings
        minTimeToMaturity = _minTimeToMaturity;
    }

    function setIsHedgingEnabled(bool _isHedgingEnabled, bool force)
        external
        onlyVaultManagers
    {
        // if there is an active hedge, we need to force the disabling
        if (force || (activeHedgeID == 0)) {
            isHedgingEnabled = _isHedgingEnabled;
        }
    }

    function setHedgeBudget(uint256 _hedgeBudget) external onlyVaultManagers {
        require(_hedgeBudget <= RATIO_PRECISION);
        hedgeBudget = _hedgeBudget;
    }

    function setHedgingPeriod(uint256 _period) external onlyVaultManagers {
        require(_period <= 90 days);
        period = _period;
    }

    function setProtectionRange(uint256 _protectionRange)
        external
        onlyVaultManagers
    {
        require(_protectionRange <= RATIO_PRECISION);
        protectionRange = _protectionRange;
    }

    function closeHedgeManually() external onlyVaultManagers {
        _closeHedge();
    }

    function resetHedge() external onlyGovernance {
        activeHedgeID = 0;
    }

    function hedgeLP()
        internal
        override
        returns (uint256 costA, uint256 costB)
    {
        if (hedgeBudget == 0 || !isHedgingEnabled) {
            return (0, 0);
        }

        // take into account that if hedgeBudget is not enough, it will revert
        IERC20 _pair = IERC20(getPair());
        uint256 initialBalanceA = balanceOfA();
        uint256 initialBalanceB = balanceOfB();
        // Only able to open a new position if no active options
        require(activeHedgeID == 0); // dev: already-open
        uint256 strikePrice;
        (activeHedgeID, strikePrice) = IHedgilPool(hedgilPool).hedgeLPToken(
            address(_pair),
            protectionRange,
            period
        );

        require(
            _isWithinRange(strikePrice, maxSlippageOpen) || skipManipulatedCheck
        ); // dev: !open-price

        // NOTE: hedge is always paid in tokenB, so costA is always = 0
        costB = initialBalanceB.sub(balanceOfB());
    }

    function closeHedge() internal override {
        // only close hedge if a hedge is open
        if (activeHedgeID == 0 || !isHedgingEnabled) {
            return;
        }

        _closeHedge();
    }

    function _closeHedge() internal {
        (, uint256 exercisePrice) =
            IHedgilPool(hedgilPool).closeHedge(activeHedgeID);

        require(
            _isWithinRange(exercisePrice, maxSlippageClose) ||
                skipManipulatedCheck
        ); // dev: !close-price
        activeHedgeID = 0;
    }

    function _isWithinRange(uint256 oraclePrice, uint256 maxSlippage)
        internal
        view
        returns (bool)
    {
        if (oraclePrice == 0) {
            return false;
        }

        uint256 tokenADecimals =
            uint256(10)**uint256(IERC20Extended(tokenA).decimals());
        uint256 tokenBDecimals =
            uint256(10)**uint256(IERC20Extended(tokenB).decimals());

        (uint256 reserveA, uint256 reserveB) = getReserves();
        uint256 currentPairPrice =
            reserveB.mul(tokenADecimals).mul(PRICE_DECIMALS).div(reserveA).div(
                tokenBDecimals
            );
        // This is a price check to avoid manipulated pairs. It checks current pair price vs hedging protocol oracle price (i.e. exercise)
        // we need pairPrice ⁄ oraclePrice to be within (1+maxSlippage) and (1-maxSlippage)
        // otherwise, we consider the price manipulated
        return
            currentPairPrice > oraclePrice
                ? currentPairPrice.mul(RATIO_PRECISION).div(oraclePrice) <
                    RATIO_PRECISION.add(maxSlippage)
                : currentPairPrice.mul(RATIO_PRECISION).div(oraclePrice) >
                    RATIO_PRECISION.sub(maxSlippage);
    }

    function shouldEndEpoch() public view override returns (bool) {
        // End epoch if price moved too much (above / below the protectionRange) or hedge is about to expire
        if (activeHedgeID == 0) {
            return false;
        }
        // if Time to Maturity of hedge is lower than min threshold, need to end epoch NOW
        if (
            IHedgilPool(hedgilPool).getTimeToMaturity(activeHedgeID) <=
            minTimeToMaturity
        ) {
            return true;
        }

        // NOTE: the initial price is calculated using the added liquidity
        uint256 tokenADecimals =
            uint256(10)**uint256(IERC20Extended(tokenA).decimals());
        uint256 tokenBDecimals =
            uint256(10)**uint256(IERC20Extended(tokenB).decimals());
        uint256 initPrice =
            investedB
                .mul(tokenADecimals)
                .mul(PRICE_DECIMALS)
                .div(investedA)
                .div(tokenBDecimals);
        return !_isWithinRange(initPrice, protectionRange);
    }

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        if (activeHedgeID == 0) {
            return false;
        }

        // if we are closing the position before 50% of hedge period has passed, we did something wrong so auto-init is stopped
        uint256 timeToMaturity = getTimeToMaturity();

        // NOTE: if timeToMaturity is 0, it means that the epoch has finished without being exercised
        // Something might be wrong so we don't start new epochs
        if (timeToMaturity == 0 || timeToMaturity > period.mul(50).div(100)) {
            return true;
        }
    }
}
