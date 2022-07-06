// SPDX-License-Identifier: BUSL-1.1

pragma solidity ^0.8.9;

import {TickMath} from "./TickMath.sol";
import {LiquidityAmounts} from "./LiquidityAmounts.sol";

/// @title Testing library conrtaining useful functions for the test suite
library TestingLibrary {

    function getSqrtRatioAtTick(int24 tick)
        external
        pure
        returns (uint160 sqrtPriceX96)
    {
        return TickMath.getSqrtRatioAtTick(tick);
    }

    function getTickAtSqrtRatio(uint160 sqrtPriceX96)
        external
        pure
        returns (int24 tick)
    {
        return TickMath.getTickAtSqrtRatio(sqrtPriceX96);
    }

    function getAmountsForLiquidity(
        uint160 sqrtRatioX96,
        uint160 sqrtRatioAX96,
        uint160 sqrtRatioBX96,
        uint128 liquidity
    ) external pure returns (uint256 amount0, uint256 amount1) {
        return LiquidityAmounts.getAmountsForLiquidity(sqrtRatioX96, sqrtRatioAX96, sqrtRatioBX96, liquidity);
    }

    function getLiquidityForAmounts(
        uint160 sqrtRatioX96,
        uint160 sqrtRatioAX96,
        uint160 sqrtRatioBX96,
        uint256 amount0,
        uint256 amount1
    ) external pure returns (uint128 liquidity) {
        return LiquidityAmounts.getLiquidityForAmounts(sqrtRatioX96, 
        sqrtRatioAX96,
        sqrtRatioBX96, 
        amount0,
        amount1
        );
    }
}
