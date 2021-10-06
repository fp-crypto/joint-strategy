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

    // HEDGING
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
            require(activeCallID == 0 && activePutID == 0);
            uint256 strikePrice;
            (activeCallID, activePutID, strikePrice) = LPHedgingLib
                .hedgeLPToken(address(_pair), protectionRange, period);
            uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
            uint256 tokenBDecimals = IERC20Extended(tokenB).decimals();
            (uint256 reserveA, uint256 reserveB) = getReserves();
            uint256 currentPairPrice =
                reserveB
                    .mul(tokenADecimals)
                    .mul(PRICE_DECIMALS)
                    .div(reserveA)
                    .div(tokenBDecimals);

            // This is a price check to avoid manipulated pairs. It checks current pair price vs hedging protocol oracle price (i.e. strike)
            require(
                currentPairPrice > strikePrice
                    ? currentPairPrice.mul(RATIO_PRECISION).div(strikePrice) <
                        maxSlippageOpen.add(RATIO_PRECISION)
                    : strikePrice.mul(RATIO_PRECISION).div(currentPairPrice) <
                        maxSlippageOpen.add(RATIO_PRECISION)
            );

            costA = initialBalanceA.sub(balanceOfA());
            costB = initialBalanceB.sub(balanceOfB());
        }
    }

    function closeHedge() internal override {
        // only close hedge if a hedge is open
        uint256 exercisePrice;
        if (activeCallID != 0 && activePutID != 0 && !isHedgingDisabled) {
            (, , exercisePrice) = LPHedgingLib.closeHedge(
                activeCallID,
                activePutID
            );
        }

        uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
        uint256 tokenBDecimals = IERC20Extended(tokenB).decimals();
        (uint256 reserveA, uint256 reserveB) = getReserves();
        uint256 currentPairPrice =
            reserveB.mul(tokenADecimals).mul(PRICE_DECIMALS).div(reserveA).div(
                tokenBDecimals
            );

        // This is a price check to avoid manipulated pairs. It checks current pair price vs hedging protocol oracle price (i.e. exercise)
        require(
            currentPairPrice > exercisePrice
                ? currentPairPrice.mul(RATIO_PRECISION).div(exercisePrice) <
                    maxSlippageClose.add(RATIO_PRECISION)
                : exercisePrice.mul(RATIO_PRECISION).div(currentPairPrice) <
                    maxSlippageClose.add(RATIO_PRECISION)
        );

        activeCallID = 0;
        activePutID = 0;
    }

    function shouldEndEpoch() public view override returns (bool) {
        // End epoch if price moved too much (above / below the protectionRange) or hedge is about to expire
        if (activeCallID != 0 || activePutID != 0) {
            // if Time to Maturity of hedge is lower than min threshold, need to end epoch
            if (
                LPHedgingLib.getTimeToMaturity(activeCallID, activePutID) <=
                minTimeToMaturity
            ) {
                return true;
            }

            (uint256 reserveA, uint256 reserveB) = getReserves();
            uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
            uint256 currentPrice = reserveB.mul(tokenADecimals).div(reserveA);
            uint256 initPrice = investedB.mul(tokenADecimals).div(investedA);

            return
                currentPrice > initPrice
                    ? currentPrice.mul(RATIO_PRECISION).div(initPrice) >
                        RATIO_PRECISION.add(protectionRange)
                    : initPrice.mul(RATIO_PRECISION).div(currentPrice) <
                        RATIO_PRECISION.sub(protectionRange);
        }

        return super.shouldEndEpoch();
    }

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        // if we are closing the position before 50% of hedge period has passed, we did something wrong so auto-init is stopped
        if (
            LPHedgingLib.getTimeToMaturity(activeCallID, activePutID) >
            period.mul(50).div(100)
        ) {
            return true;
        }
        return super._autoProtect();
    }
}
