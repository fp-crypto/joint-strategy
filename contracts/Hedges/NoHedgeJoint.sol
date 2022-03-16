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

abstract contract NoHedgeJoint is Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward
    ) public Joint(_providerA, _providerB, _router, _weth, _reward) {}

    function getHedgeBudget(address token)
        public
        view
        override
        returns (uint256)
    {
        return 0;
    }

    function getTimeToMaturity() public view returns (uint256) {
        return 0;
    }

    function getHedgeProfit() public view override returns (uint256, uint256) {
        return (0, 0);
    }

    function hedgeLP()
        internal
        override
        returns (uint256 costA, uint256 costB)
    {
        // NO HEDGE
        return (0, 0);
    }

    function closeHedge() internal override {
        // NO HEDGE
        return;
    }

    function shouldEndEpoch() public view override returns (bool) {
        return false;
    }

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        return false;
    }
}
