// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

import "../Joint.sol";

abstract contract NoHedgeJoint is Joint {
    constructor(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool
    ) Joint(_providerA, _providerB, _weth, _pool) {}

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

    // this function is called by Joint to see if it needs to stop initiating new epochs due to too high volatility
    function _autoProtect() internal view override returns (bool) {
        return false;
    }
}
