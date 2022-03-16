// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;


interface ISolidex {
    struct Amounts {
        uint256 solid;
        uint256 sex;
    }

    function deposit(address _pair, uint256 _amount) external; 
    function withdraw(address _pair, uint256 _amount) external; 
    function getReward(address[] calldata _pairs) external; 
    function pendingRewards(address _account, address[] calldata pairs) external view returns (Amounts[] memory);
    function userBalances(address _account, address _pair) external view returns (uint256);
}


