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

    uint256 public hedgeBudget; // 0.5% per hedging period
    uint256 public protectionRange; // 10%
    uint256 public period;

    uint256 private minTimeToMaturity;

    // HEDGING
    bool public isHedgingDisabled;

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

    function getHedgeBudget() public override returns (uint256) {
        return hedgeBudget;
    }

    function getHedgeProfit() public view override returns (uint256, uint256) {
        return LPHedgingLib.getOptionsProfit(activeCallID, activePutID);
    }

    function setMinTimeToMaturity(uint256 _minTimeToMaturity) external onlyAuthorized {
	require(_minTimToMaturity > period); // avoid incorrect settings
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
            (activeCallID, activePutID) = LPHedgingLib.hedgeLPToken(
                address(_pair),
                protectionRange,
                period
            );
            costA = initialBalanceA.sub(balanceOfA());
            costB = initialBalanceB.sub(balanceOfB());
        }
    }

    function closeHedge() internal override {
        // only close hedge if a hedge is open
        if (activeCallID != 0 && activePutID != 0 && !isHedgingDisabled) {
            LPHedgingLib.closeHedge(activeCallID, activePutID);
        }

        activeCallID = 0;
        activePutID = 0;
    }

    function shouldEndEpoch() public override returns (bool) {
	// End epoch if price moved too much (above / below the protectionRange) or hedge is about to expire
	if(activeCallID != 0 || activePutID != 0) {
	    // if Time to Maturity of hedge is lower than min threshold, need to end epoch
	    if(LPHedgingLib.getTimeToMaturity(activeCallID, activePutID) <= minTimeToMaturity) {
		    return true;
	    }

	    uint256 tokenADecimals = IERC20Extended(tokenA).decimals();
	    uint256 currentPrice = estimatedTotalAssetsInToken(tokenB).mul(tokenADecimals).div(estimatedTotalAssetsInToken(tokenA));
	    uint256 initPrice = investedB.mul(tokenADecimals).div(investedA);

	    return currentPrice > initPrice ?
		    currentPrice.mul(RATIO_PRECISION).div(initPrice) > RATIO_PRECISION.add(protectionRange) :
		    initPrice.mul(RATIO_PRECISION).div(currentPrice) > RATIO_PRECISION.sub(protectionRange);
	}

	return super.shouldEndEpoch();
    }

    function _ratioThreshold() public returns (uint) {
	// 7% should be close to 15% price change
	return uint256(7).mul(RATIO_PRECISION).div(100);
    }
}
