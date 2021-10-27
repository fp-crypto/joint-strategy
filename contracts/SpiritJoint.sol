// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./Joint.sol";

interface ISpiritMasterchef is IMasterchef {
    function pendingSpirit(uint256 _pid, address _user)
        external
        view
        returns (uint256);
}

contract SpiritJoint is Joint {
    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _masterchef,
        address _reward,
        uint256 _pid
    )
        public
        Joint(
            _providerA,
            _providerB,
            _router,
            _weth,
            _masterchef,
            _reward,
            _pid
        )
    {}

    function name() external view override returns (string memory) {
        string memory ab =
            string(
                abi.encodePacked(
                    IERC20Extended(address(tokenA)).symbol(),
                    IERC20Extended(address(tokenB)).symbol()
                )
            );

        return string(abi.encodePacked("SpiritJointOf", ab));
    }

    function pendingReward() public view override returns (uint256) {
        return
            ISpiritMasterchef(address(masterchef)).pendingSpirit(
                pid,
                address(this)
            );
    }
}
