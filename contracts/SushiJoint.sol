// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "./HegicJoint.sol";

interface ISushiMasterchef is IMasterchef {
    function pendingSushi(uint256 _pid, address _user)
        external
        view
        returns (uint256);
}

contract SushiJoint is HegicJoint {
    uint256 public pid;

    IMasterchef public masterchef;
    bool public dontWithdraw;

    bool public isOriginal = true;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _hegicCallOptionsPool,
        address _hegicPutOptionsPool,
        address _masterchef,
        uint256 _pid
    )
        public
        HegicJoint(
            _providerA,
            _providerB,
            _router,
            _weth,
            _reward,
            _hegicCallOptionsPool,
            _hegicPutOptionsPool
        )
    {
        _initalizeSushiJoint(_masterchef, _pid);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _hegicCallOptionsPool,
        address _hegicPutOptionsPool,
        address _masterchef,
        uint256 _pid
    ) external {
        _initialize(_providerA, _providerB, _router, _weth, _reward);
        _initializeHegicJoint(_hegicCallOptionsPool, _hegicPutOptionsPool);
        _initalizeSushiJoint(_masterchef, _pid);
    }

    function _initalizeSushiJoint(address _masterchef, uint256 _pid) internal {
        masterchef = IMasterchef(_masterchef);
        pid = _pid;

        IERC20(address(pair)).approve(_masterchef, type(uint256).max);
    }

    event Cloned(address indexed clone);

    function cloneSushiJoint(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _hegicCallOptionsPool,
        address _hegicPutOptionsPool,
        address _masterchef,
        uint256 _pid
    ) external returns (address newJoint) {
        require(isOriginal, "!original");
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

        SushiJoint(newJoint).initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _reward,
            _hegicCallOptionsPool,
            _hegicPutOptionsPool,
            _masterchef,
            _pid
        );

        emit Cloned(newJoint);
    }

    function name() external view override returns (string memory) {
        string memory ab =
            string(
                abi.encodePacked(
                    IERC20Extended(address(tokenA)).symbol(),
                    "-",
                    IERC20Extended(address(tokenB)).symbol()
                )
            );

        return string(abi.encodePacked("HegicSushiJoint(", ab, ")"));
    }

    function balanceOfStake() public view override returns (uint256) {
        return masterchef.userInfo(pid, address(this)).amount;
    }

    function pendingReward() public view override returns (uint256) {
        return
            ISushiMasterchef(address(masterchef)).pendingSushi(
                pid,
                address(this)
            );
    }

    function getReward() internal override {
        masterchef.deposit(pid, 0);
    }

    function setDontWithdraw(bool _dontWithdraw) external onlyVaultManagers {
        dontWithdraw = _dontWithdraw;
    }

    function depositLP() internal override {
        if (balanceOfPair() > 0) {
            masterchef.deposit(pid, balanceOfPair());
        }
    }

    function withdrawLP() internal override {
        uint256 stakeBalance = balanceOfStake();
        if (stakeBalance > 0 && !dontWithdraw) {
            masterchef.withdraw(pid, stakeBalance);
        }
    }

    function withdrawLPManually(uint256 amount) external onlyVaultManagers {
        masterchef.withdraw(pid, amount);
    }
}
