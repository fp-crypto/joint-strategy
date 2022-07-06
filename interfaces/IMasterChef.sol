pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

interface IMasterchef {
    // Info of each pool.
    struct PoolInfo {
        address lpToken; // Address of LP token contract.
        uint256 allocPoint; // How many allocation points assigned to this pool. Tokenss to distribute per block.
        uint256 lastRewardBlock; // Last block number that Tokens distribution occurs.
        uint256 acctokenPerShare; // Accumulated Tokens per share, times 1e12. See below.
    }

    // Info of each user.
    struct UserInfo {
        uint256 amount; // How many LP tokens the user has provided.
        uint256 rewardDebt; // Reward debt.
    }

    function deposit(uint256 _pid, uint256 _amount) external;

    function withdraw(uint256 _pid, uint256 _amount) external;

    function userInfo(uint256, address) external view returns (UserInfo memory);

    function poolInfo(uint256) external view returns (PoolInfo memory);
}
