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
import "../libraries/LPHedgingLib.sol";
import "../Joint.sol";

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
    bool public isHedgingEnabled;

    uint256 private constant PRICE_DECIMALS = 1e8;
    uint256 public maxSlippageOpen;
    uint256 public maxSlippageClose;

    address public hegicCallOptionsPool;
    address public hegicPutOptionsPool;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _hegicCallOptionsPool,
        address _hegicPutOptionsPool
    ) public Joint(_providerA, _providerB, _router, _weth, _reward) {
        _initializeHegicJoint(_hegicCallOptionsPool, _hegicPutOptionsPool);
    }

    function _initializeHegicJoint(
        address _hegicCallOptionsPool,
        address _hegicPutOptionsPool
    ) internal {
        hegicCallOptionsPool = _hegicCallOptionsPool;
        hegicPutOptionsPool = _hegicPutOptionsPool;

        hedgeBudget = 50; // 0.5% per hedging period
        protectionRange = 1000; // 10%
        period = 7 days;
        minTimeToMaturity = 3600; // 1 hour
        maxSlippageOpen = 100; // 1%
        maxSlippageClose = 100; // 1%

        isHedgingEnabled = true;
    }

    function onERC721Received(
        address,
        address,
        uint256,
        bytes calldata
    ) public pure virtual returns (bytes4) {
        return this.onERC721Received.selector;
    }

    function getHedgeBudget(address token)
        public
        view
        override
        returns (uint256)
    {
        return hedgeBudget;
    }

    function getTimeToMaturity() public view returns (uint256) {
        return LPHedgingLib.getTimeToMaturity(activeCallID, activePutID);
    }

    function getHedgeProfit() public view override returns (uint256, uint256) {
        return LPHedgingLib.getOptionsProfit(activeCallID, activePutID);
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
        if (force || (activeCallID == 0 && activePutID == 0)) {
            isHedgingEnabled = _isHedgingEnabled;
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
        activeCallID = 0;
        activePutID = 0;
    }

    function getHedgeStrike() internal view returns (uint256) {
        return LPHedgingLib.getHedgeStrike(activeCallID, activePutID);
    }

    function closeHedgeManually(uint256 callID, uint256 putID)
        external
        onlyVaultManagers
    {
        (, , uint256 exercisePrice) = LPHedgingLib.closeHedge(callID, putID);
        require(
            _isWithinRange(exercisePrice, maxSlippageClose) ||
                skipManipulatedCheck
        ); // dev: !close-price
        activeCallID = 0;
        activePutID = 0;
    }

    function hedgeLP()
        internal
        override
        returns (uint256 costA, uint256 costB)
    {
        if (hedgeBudget > 0 && isHedgingEnabled) {
            // take into account that if hedgeBudget is not enough, it will revert
            IERC20 _pair = IERC20(getPair());
            uint256 initialBalanceA = balanceOfA();
            uint256 initialBalanceB = balanceOfB();
            // Only able to open a new position if no active options
            require(activeCallID == 0 && activePutID == 0); // dev: opened
            uint256 strikePrice;
            (activeCallID, activePutID, strikePrice) = LPHedgingLib
                .hedgeLPToken(address(_pair), protectionRange, period);

            require(
                _isWithinRange(strikePrice, maxSlippageOpen) ||
                    skipManipulatedCheck
            ); // dev: !open-price

            costA = initialBalanceA.sub(balanceOfA());
            costB = initialBalanceB.sub(balanceOfB());
        }
    }

    function closeHedge() internal override {
        uint256 exercisePrice;
        // only close hedge if a hedge is open
        if (activeCallID != 0 && activePutID != 0 && isHedgingEnabled) {
            (, , exercisePrice) = LPHedgingLib.closeHedge(
                activeCallID,
                activePutID
            );
            require(
                _isWithinRange(exercisePrice, maxSlippageClose) ||
                    skipManipulatedCheck
            ); // dev: !close-price
            activeCallID = 0;
            activePutID = 0;
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
        if (activeCallID != 0 || activePutID != 0) {
            // if Time to Maturity of hedge is lower than min threshold, need to end epoch NOW
            if (
                LPHedgingLib.getTimeToMaturity(activeCallID, activePutID) <=
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
        if (activeCallID != 0 && activePutID != 0) {
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
