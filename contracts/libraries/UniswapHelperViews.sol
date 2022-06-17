// SPDX-License-Identifier: BUSL-1.1

pragma solidity ^0.8.9;

import {FullMath} from "./FullMath.sol";
import {FixedPoint128} from "./FixedPoint128.sol";
import {SwapMath} from "./SwapMath.sol";
import {SafeCast} from "./SafeCast.sol";
import {TickMath} from "./TickMath.sol";
import {LiquidityAmounts} from "./LiquidityAmounts.sol";
import {TickBitmapExtended} from "./TickBitmapExtended.sol";

// import {IUniswapV3Pool} from "../../interfaces/uniswap/V3/IUniswapV3Pool.sol";
import {Simulate} from "@uniswap/contracts/libraries/Simulate.sol";
import {IUniswapV3Pool} from "@uniswap/contracts/interfaces/IUniswapV3Pool.sol";

/// @title Uniswap V3 necessary views for the strategy
library UniswapHelperViews {
    using SafeCast for uint256;
    using TickBitmapExtended for function(int16)
        external
        view
        returns (uint256);

    error ZeroAmount();
    error InvalidSqrtPriceLimit(uint160 sqrtPriceLimitX96);

    uint256 public constant PRECISION = 1e18;

    /// @notice Simulates a swap over an Uniswap V3 Pool, allowing to handle tick crosses.
    /// @param v3Pool uniswap v3 pool address
    /// @param zeroForOne direction of swap, true means swap zero for one
    /// @param amountSpecified amount to swap in/out
    /// @param sqrtPriceLimitX96 the maximum price to swap to, if this price is reached, then the swap is stopped partially
    /// @return amount0 token0 amount
    /// @return amount1 token1 amount
    function simulateSwap(
        address v3Pool,
        bool zeroForOne,
        int256 amountSpecified,
        uint160 sqrtPriceLimitX96
    )
        external
        view
        returns (
            int256, int256 
        )
    {  
        return Simulate.simulateSwap(IUniswapV3Pool(v3Pool), zeroForOne, amountSpecified, sqrtPriceLimitX96);
    }

    struct feesEarnedParams {
        address v3Pool;
        uint128 liquidity;
        int24 tickCurrent;
        int24 tickLower;
        int24 tickUpper;
        uint256 feeGrowthGlobal0X128;
        uint256 feeGrowthGlobal1X128;
        uint256 feeGrowthInside0LastX128;
        uint256 feeGrowthInside1LastX128;
    }

    /// @notice Retrieves owed fee data for a specific position
    /// @param _feesEarnedParams Custom struct containing:
    /// - liquidity Position's liquidity
    /// - tickCurrent The current tick
    /// - tickLower The lower tick boundary of the position
    /// - tickUpper The upper tick boundary of the position
    /// - feeGrowthGlobal0X128 The all-time global fee growth, per unit of liquidity, in token0
    /// - feeGrowthGlobal1X128 The all-time global fee growth, per unit of liquidity, in token1
    /// - feeGrowthInside0X128 The all-time fee growth in token0, per unit of liquidity, inside the position's tick boundaries
    /// - feeGrowthInside1X128 The all-time fee growth in token1, per unit of liquidity, inside the position's tick boundaries
    function getFeesEarned(
        feesEarnedParams memory _feesEarnedParams
    ) internal view returns (uint128 tokensOwed0, uint128 tokensOwed1) {
        uint256 feeGrowthBelow0X128;
        uint256 feeGrowthBelow1X128;
        IUniswapV3Pool _pool = IUniswapV3Pool(_feesEarnedParams.v3Pool);
        (,,uint256 lower_feeGrowthOutside0X128, uint256 lower_feeGrowthOutside1X128,,,,) = _pool.ticks(_feesEarnedParams.tickLower);
        (,,uint256 upper_feeGrowthOutside0X128, uint256 upper_feeGrowthOutside1X128,,,,) = _pool.ticks(_feesEarnedParams.tickUpper);

        if (_feesEarnedParams.tickCurrent >= _feesEarnedParams.tickLower) {
            feeGrowthBelow0X128 = lower_feeGrowthOutside0X128;
            feeGrowthBelow1X128 = lower_feeGrowthOutside1X128;
        } else {
            feeGrowthBelow0X128 =
                _feesEarnedParams.feeGrowthGlobal0X128 -
                lower_feeGrowthOutside0X128;
            feeGrowthBelow1X128 =
                _feesEarnedParams.feeGrowthGlobal1X128 -
                lower_feeGrowthOutside1X128;
        }

        // calculate fee growth above
        uint256 feeGrowthAbove0X128;
        uint256 feeGrowthAbove1X128;
        if (_feesEarnedParams.tickCurrent < _feesEarnedParams.tickUpper) {
            feeGrowthAbove0X128 = upper_feeGrowthOutside0X128;
            feeGrowthAbove1X128 = upper_feeGrowthOutside1X128;
        } else {
            feeGrowthAbove0X128 =
                _feesEarnedParams.feeGrowthGlobal0X128 -
                upper_feeGrowthOutside0X128;
            feeGrowthAbove1X128 =
                _feesEarnedParams.feeGrowthGlobal1X128 -
                upper_feeGrowthOutside1X128;
        }

        uint256 feeGrowthInside0X128 = _feesEarnedParams.feeGrowthGlobal0X128 -
            feeGrowthBelow0X128 -
            feeGrowthAbove0X128;
        uint256 feeGrowthInside1X128 = _feesEarnedParams.feeGrowthGlobal1X128 -
            feeGrowthBelow1X128 -
            feeGrowthAbove1X128;

        // calculate accumulated fees
        tokensOwed0 = uint128(
            FullMath.mulDiv(
                feeGrowthInside0X128 -
                    _feesEarnedParams.feeGrowthInside0LastX128,
                _feesEarnedParams.liquidity,
                FixedPoint128.Q128
            )
        );
        tokensOwed1 = uint128(
            FullMath.mulDiv(
                feeGrowthInside1X128 -
                    _feesEarnedParams.feeGrowthInside1LastX128,
                _feesEarnedParams.liquidity,
                FixedPoint128.Q128
            )
        );
    }
}
