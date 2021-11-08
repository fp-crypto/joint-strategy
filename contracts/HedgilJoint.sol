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
import "./Joint.sol";

interface IHedgilPool {
    function getTimeToMaturity(uint256 hedgeID) external view returns (uint256);

    function getHedgeProfit(uint256 hedgeID) external view returns (uint256);

    function getHedgeStrike(uint256 hedgeID) external view returns (uint256);

    function hedgeLPToken(
        address pair,
        uint256 protectionRange,
        uint256 period
    ) external returns (uint256, uint256);

    function closeHedge(uint256 hedgedID)
        external
        returns (uint256 payoff, uint256 exercisePrice);
}

abstract contract HedgilJoint is Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 private constant PRICE_DECIMALS = 1e8;

    uint256 public activeHedgeID;

    uint256 public hedgeBudget;
    uint256 public protectionRange;
    uint256 public period;

    uint256 private minTimeToMaturity;

    bool public skipManipulatedCheck;
    bool public isHedgingDisabled;

    uint256 public maxSlippageOpen;
    uint256 public maxSlippageClose;

    address public hedgilPool;

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
        hedgeBudget = 50; // 0.5% per hedging period
        protectionRange = 1000; // 10%
        period = 7 days;
        minTimeToMaturity = 3600; // 1 hour
        maxSlippageOpen = 100; // 1%
        maxSlippageClose = 100; // 1%
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
        return (IHedgilPool(hedgilPool).getHedgeProfit(activeHedgeID), 0);
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
        maxSlippageClose = _maxSlippageClose;
    }

    function setMaxSlippageOpen(uint256 _maxSlippageOpen)
        external
        onlyVaultManagers
    {
        maxSlippageOpen = _maxSlippageOpen;
    }

    function setMinTimeToMaturity(uint256 _minTimeToMaturity)
        external
        onlyVaultManagers
    {
        require(_minTimeToMaturity <= period); // avoid incorrect settings
        minTimeToMaturity = _minTimeToMaturity;
    }

    function setIsHedgingDisabled(bool _isHedgingDisabled, bool force)
        external
        onlyVaultManagers
    {
        // if there is an active hedge, we need to force the disabling
        if (force || (activeHedgeID == 0)) {
            isHedgingDisabled = _isHedgingDisabled;
        }
    }

    function setHedgeBudget(uint256 _hedgeBudget) external onlyVaultManagers {
        require(_hedgeBudget < RATIO_PRECISION);
        hedgeBudget = _hedgeBudget;
    }

    function setHedgingPeriod(uint256 _period) external onlyVaultManagers {
        require(_period < 90 days);
        period = _period;
    }

    function setProtectionRange(uint256 _protectionRange)
        external
        onlyVaultManagers
    {
        require(_protectionRange < RATIO_PRECISION);
        protectionRange = _protectionRange;
    }

    function resetHedge() external onlyGovernance {
        activeHedgeID = 0;
    }

    function getHedgeStrike() internal view returns (uint256) {
        return IHedgilPool(hedgilPool).getHedgeStrike(activeHedgeID);
    }

    function closeHedgeManually() external onlyVaultManagers {
        closeHedge();
    }

    function hedgeLP()
        internal
        override
        returns (uint256 costA, uint256 costB)
    {
        if (hedgeBudget > 0 && !isHedgingDisabled) {
            // take into account that if hedgeBudget is not enough, it will revert
            IERC20 _pair = IERC20(getPair());
            uint256 initialBalanceA = balanceOfA();
            uint256 initialBalanceB = balanceOfB();
            // Only able to open a new position if no active options
            require(activeHedgeID == 0);
            uint256 strikePrice;
            (activeHedgeID, strikePrice) = IHedgilPool(hedgilPool).hedgeLPToken(
                address(_pair),
                protectionRange,
                period
            );

            require(
                _isWithinRange(strikePrice, maxSlippageOpen) ||
                    skipManipulatedCheck,
                "!open price looks manipulated"
            );

            costA = initialBalanceA.sub(balanceOfA());
            costB = initialBalanceB.sub(balanceOfB());
        }
    }

    function closeHedge() internal override {
        uint256 exercisePrice;
        // only close hedge if a hedge is open
        if (activeHedgeID != 0 && !isHedgingDisabled) {
            (, exercisePrice) = IHedgilPool(hedgilPool).closeHedge(
                activeHedgeID
            );
            require(
                _isWithinRange(exercisePrice, maxSlippageClose) ||
                    skipManipulatedCheck,
                "!close price looks manipulated"
            );
            activeHedgeID = 0;
        }
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
        if (activeHedgeID != 0) {
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
    }

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        // if we are closing the position before 50% of hedge period has passed, we did something wrong so auto-init is stopped
        uint256 timeToMaturity = getTimeToMaturity();
        if (activeHedgeID != 0) {
            // NOTE: if timeToMaturity is 0, it means that the epoch has finished without being exercised
            // Something might be wrong so we don't start new epochs
            if (
                timeToMaturity == 0 || timeToMaturity > period.mul(50).div(100)
            ) {
                return true;
            }
        }
    }
}
