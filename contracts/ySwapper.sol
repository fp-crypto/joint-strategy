// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {
    SafeERC20,
    IERC20
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

interface ITradeFactory {
    function enable(address, address) external;
}

abstract contract ySwapper {
    using SafeERC20 for IERC20;
    // TODO: not working for clonables ! 
    address public tradeFactory =
        address(0xD3f89C21719Ec5961a3E6B0f9bBf9F9b4180E9e9);

    bool public tradesEnabled;
   
    // Implement in contract using ySwaps. 
    // should return the list of tokens to be swapped and a list of tokens to be swapped to
    function getYSwapTokens() internal view virtual returns (address[] memory, address[] memory);

    // WARNING this is a manual permissioned function
    // should call internalFunction and use onlyROLEs
    // if you don't want this function, just override with empty function
    function removeTradeFactoryPermissions() external virtual;
    
    // WARNING this is a manual permissioned function
    // should call internalFunction and use onlyROLEs
    // if you don't want this function, just override with empty function
    function updateTradeFactoryPermissions(address _tradeFactory) external virtual;

    function _setUpTradeFactory() internal {
        //approve and set up trade factory
        tradesEnabled = true;
        (address[] memory tokensToEnable, address[] memory toTokens) = getYSwapTokens();

        for(uint i; i < tokensToEnable.length; i++) {
            _enableTradeFactoryForToken(tokensToEnable[i], toTokens[i]);
        }
    }
 
    function _enableTradeFactoryForToken(address fromToken, address toToken) internal {
        ITradeFactory tf = ITradeFactory(tradeFactory);
        IERC20(fromToken).safeApprove(address(tf), type(uint256).max);
        tf.enable(fromToken, toToken);
    }

    function _updateTradeFactory(address _newTradeFactory)
       internal 
    {
        if (tradeFactory != address(0)) {
            _removeTradeFactory();
        }

        tradeFactory = _newTradeFactory;
        _setUpTradeFactory();
    }

    function _removeTradeFactory() internal {
        address _tradeFactory = tradeFactory;
 
        (address[] memory tokens, ) = getYSwapTokens();

        for(uint i = 0; i < tokens.length; i++) {
            IERC20(tokens[i]).safeApprove(_tradeFactory, 0);
        }

        tradeFactory = address(0);
        tradesEnabled = false;
    }
}
