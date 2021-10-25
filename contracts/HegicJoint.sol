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

abstract contract HegicJoint is Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    uint256 public activeCallID;
    uint256 public activePutID;

    uint256 public hedgeBudget;
    uint256 public protectionRange;
    uint256 public period;

    uint256 private minTimeToMaturity;

    bool public skipManipulatedCheck;
    bool public isHedgingDisabled;

    uint256 private constant PRICE_DECIMALS = 8;
    uint256 private maxSlippageOpen;
    uint256 private maxSlippageClose;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward
    ) public Joint(_providerA, _providerB, _router, _weth, _reward) {}

    function _initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward
    ) internal override {
        super._initialize(_providerA, _providerB, _router, _weth, _reward);

        hedgeBudget = 50; // 0.5% per hedging period
        protectionRange = 1000; // 10%
        period = 1 days;
        minTimeToMaturity = 3600; // 1 hour
    }

    function onERC721Received(
        address,
        address,
        uint256,
        bytes calldata
    ) public pure virtual returns (bytes4) {
        return this.onERC721Received.selector;
    }

    function getHedgeBudget(address token) public override returns (uint256) {
        return hedgeBudget;
    }

    function getHedgeProfit() public view override returns (uint256, uint256) {
        return LPHedgingLib.getOptionsProfit(activeCallID, activePutID);
    }

    function setSkipManipulatedCheck(bool _skipManipulatedCheck)
        external
        onlyAuthorized
    {
        skipManipulatedCheck = _skipManipulatedCheck;
    }

    function setMaxSlippageClose(uint256 _maxSlippageClose)
        external
        onlyAuthorized
    {
        maxSlippageClose = _maxSlippageClose;
    }

    function setMaxSlippageOpen(uint256 _maxSlippageOpen)
        external
        onlyAuthorized
    {
        maxSlippageOpen = _maxSlippageOpen;
    }

    function setMinTimeToMaturity(uint256 _minTimeToMaturity)
        external
        onlyAuthorized
    {
        require(_minTimeToMaturity > period); // avoid incorrect settings
        minTimeToMaturity = _minTimeToMaturity;
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

    function resetHedge() external onlyGovernance {
        activeCallID = 0;
        activePutID = 0;
    }

    function getHedgeStrike() internal view returns (uint256) {
        return LPHedgingLib.getHedgeStrike(activeCallID, activePutID);
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
            require(activeCallID == 0 && activePutID == 0);
            uint256 strikePrice;
            (activeCallID, activePutID, strikePrice) = LPHedgingLib
                .hedgeLPToken(address(_pair), protectionRange, period);

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
        if (activeCallID != 0 && activePutID != 0 && !isHedgingDisabled) {
            (, , exercisePrice) = LPHedgingLib.closeHedge(
                activeCallID,
                activePutID
            );
        }

        require(
            _isWithinRange(exercisePrice, maxSlippageClose) ||
                skipManipulatedCheck,
            "!close price looks manipulated"
        );

        activeCallID = 0;
        activePutID = 0;
    }

    function _isWithinRange(uint256 oraclePrice, uint256 maxSlippage)
        internal
        view
        returns (bool)
    {
        uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
        uint256 tokenBDecimals = IERC20Extended(tokenB).decimals();
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
        if (activeCallID != 0 || activePutID != 0) {
            // if Time to Maturity of hedge is lower than min threshold, need to end epoch NOW
            if (
                LPHedgingLib.getTimeToMaturity(activeCallID, activePutID) <=
                minTimeToMaturity
            ) {
                return true;
            }

            // NOTE: the initial price is calculated using the added liquidity
            uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
            uint256 tokenBDecimals = IERC20Extended(tokenB).decimals();
            uint256 initPrice =
                investedB
                    .mul(tokenADecimals)
                    .mul(PRICE_DECIMALS)
                    .div(investedA)
                    .div(tokenBDecimals);
            return _isWithinRange(initPrice, protectionRange);
        }

        return super.shouldEndEpoch();
    }

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        // if we are closing the position before 50% of hedge period has passed, we did something wrong so auto-init is stopped
        uint256 timeToMaturity =
            LPHedgingLib.getTimeToMaturity(activeCallID, activePutID);
        if (activeCallID != 0 && activePutID != 0) {
            // NOTE: if timeToMaturity is 0, it means that the epoch has finished without being exercised
            // Something might be wrong so we don't start new epochs
            if (
                timeToMaturity == 0 || timeToMaturity > period.mul(50).div(100)
            ) {
                return true;
            }
        }
        return super._autoProtect();
    }
}
