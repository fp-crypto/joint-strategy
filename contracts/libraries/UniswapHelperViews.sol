// SPDX-License-Identifier: BUSL-1.1

pragma solidity ^0.8.9;

import {FullMath} from "./FullMath.sol";
import {FixedPoint128} from "./FixedPoint128.sol";
import {SwapMath} from "./SwapMath.sol";
import {SafeCast} from "./SafeCast.sol";
import {TickMath} from "./TickMath.sol";
import {LiquidityAmounts} from "./LiquidityAmounts.sol";
import {TickBitmapExtended} from "./TickBitmapExtended.sol";

import {IUniswapV3Pool} from "../../interfaces/uniswap/V3/IUniswapV3Pool.sol";

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

    struct Cache {
        // price at the beginning of the swap
        uint160 sqrtPriceX96Start;
        // tick at the beginning of the swap
        int24 tickStart;
        // the protocol fee for the input token
        uint8 feeProtocol;
        // liquidity at the beginning of the swap
        uint128 liquidityStart;
        // the tick spacing of the pool
        int24 tickSpacing;
        // the lp fee share of the pool
        uint24 fee;
    }

    struct State {
        // the amount remaining to be swapped in/out of the input/output asset
        int256 amountSpecifiedRemaining;
        // the amount already swapped out/in of the output/input asset
        int256 amountCalculated;
        // current sqrt(price)
        uint160 sqrtPriceX96;
        // the tick associated with the current price
        int24 tick;
        // the global fee growth of the input token
        uint256 feeGrowthGlobalIncreaseX128;
        // amount of input token paid as protocol fee
        uint128 protocolFee;
        // the current liquidity in range
        uint128 liquidity;
    }

    struct Step {
        // the price at the beginning of the step
        uint160 sqrtPriceStartX96;
        // the next tick to swap to from the current tick in the swap direction
        int24 tickNext;
        // whether tickNext is initialized or not
        bool initialized;
        // sqrt(price) for the next tick (1/0)
        uint160 sqrtPriceNextX96;
        // how much is being swapped in in this step
        uint256 amountIn;
        // how much is being swapped out
        uint256 amountOut;
        // how much fee is being paid in
        uint256 feeAmount;
    }

    /// @notice Simulates a swap over an Uniswap V3 Pool, allowing to handle tick crosses.
    /// @param v3Pool uniswap v3 pool address
    /// @param zeroForOne direction of swap, true means swap zero for one
    /// @param amountSpecified amount to swap in/out
    /// @param sqrtPriceLimitX96 the maximum price to swap to, if this price is reached, then the swap is stopped partially
    /// @param cache the swap cache, can be passed empty or with some values filled in to prevent STATICCALLS to v3Pool
    /// @return amount0 token0 amount
    /// @return amount1 token1 amount
    /// @return state swap state at the end of the swap
    function simulateSwap(
        IUniswapV3Pool v3Pool,
        bool zeroForOne,
        int256 amountSpecified,
        uint160 sqrtPriceLimitX96,
        UniswapHelperViews.Cache memory cache
    )
        internal
        view
        returns (
            int256 amount0,
            int256 amount1,
            UniswapHelperViews.State memory state
        )
    {
        if (amountSpecified == 0) revert ZeroAmount();

        // if cache.sqrtPriceX96Start is not set, then make a STATICCALL to v3Pool
        if (cache.sqrtPriceX96Start == 0) {
            IUniswapV3Pool.Slot0 memory slot0 = v3Pool.slot0();
            cache.sqrtPriceX96Start = slot0.sqrtPriceX96;
            cache.tickStart = slot0.tick;
            cache.feeProtocol = slot0.feeProtocol;
        }

        // if cache.liquidityStart is not set, then make a STATICCALL to v3Pool
        if (cache.liquidityStart == 0)
            cache.liquidityStart = v3Pool.liquidity();

        // if cache.tickSpacing is not set, then make a STATICCALL to v3Pool
        if (cache.tickSpacing == 0) {
            cache.fee = v3Pool.fee();
            cache.tickSpacing = v3Pool.tickSpacing();
        }

        // ensure that the sqrtPriceLimitX96 makes sense
        if (
            zeroForOne
                ? sqrtPriceLimitX96 > cache.sqrtPriceX96Start ||
                    sqrtPriceLimitX96 < TickMath.MIN_SQRT_RATIO
                : sqrtPriceLimitX96 < cache.sqrtPriceX96Start ||
                    sqrtPriceLimitX96 > TickMath.MAX_SQRT_RATIO
        ) revert InvalidSqrtPriceLimit(sqrtPriceLimitX96);

        bool exactInput = amountSpecified > 0;

        state = UniswapHelperViews.State({
            amountSpecifiedRemaining: amountSpecified,
            amountCalculated: 0,
            sqrtPriceX96: cache.sqrtPriceX96Start,
            tick: cache.tickStart,
            feeGrowthGlobalIncreaseX128: 0,
            protocolFee: 0,
            liquidity: cache.liquidityStart
        });

        // continue swapping as long as we haven't used the entire input/output and haven't reached the price limit
        while (
            state.amountSpecifiedRemaining != 0 &&
            state.sqrtPriceX96 != sqrtPriceLimitX96
        ) {
            UniswapHelperViews.Step memory step;

            step.sqrtPriceStartX96 = state.sqrtPriceX96;

            (step.tickNext, step.initialized) = v3Pool
                .tickBitmap
                .nextInitializedTickWithinOneWord(
                    state.tick,
                    cache.tickSpacing,
                    zeroForOne
                );

            // ensure that we do not overshoot the min/max tick, as the tick bitmap is not aware of these bounds
            if (step.tickNext < TickMath.MIN_TICK) {
                step.tickNext = TickMath.MIN_TICK;
            } else if (step.tickNext > TickMath.MAX_TICK) {
                step.tickNext = TickMath.MAX_TICK;
            }

            // get the price for the next tick
            step.sqrtPriceNextX96 = TickMath.getSqrtRatioAtTick(step.tickNext);

            // compute values to swap to the target tick, price limit, or point where input/output amount is exhausted
            (
                state.sqrtPriceX96,
                step.amountIn,
                step.amountOut,
                step.feeAmount
            ) = SwapMath.computeSwapStep(
                state.sqrtPriceX96,
                (
                    zeroForOne
                        ? step.sqrtPriceNextX96 < sqrtPriceLimitX96
                        : step.sqrtPriceNextX96 > sqrtPriceLimitX96
                )
                    ? sqrtPriceLimitX96
                    : step.sqrtPriceNextX96,
                state.liquidity,
                state.amountSpecifiedRemaining,
                cache.fee
            );

            if (exactInput) {
                state.amountSpecifiedRemaining -= (step.amountIn +
                    step.feeAmount).toInt256();
                state.amountCalculated =
                    state.amountCalculated -
                    step.amountOut.toInt256();
            } else {
                state.amountSpecifiedRemaining += step.amountOut.toInt256();
                state.amountCalculated =
                    state.amountCalculated +
                    (step.amountIn + step.feeAmount).toInt256();
            }

            // update global fee tracker
            if (state.liquidity > 0) {
                state.feeGrowthGlobalIncreaseX128 += FullMath.mulDiv(
                    step.feeAmount,
                    FixedPoint128.Q128,
                    state.liquidity
                );
            }

            // jump to the method that handles the swap step
            //onSwapStep(zeroForOne, cache, state, step);

            // shift tick if we reached the next price
            if (state.sqrtPriceX96 == step.sqrtPriceNextX96) {
                // if the tick is initialized, adjust the liquidity
                if (step.initialized) {
                    IUniswapV3Pool.TickInfo memory tickInfo = v3Pool.ticks(
                        step.tickNext
                    );
                    int128 liquidityNet = tickInfo.liquidityNet;
                    // if we're moving leftward, we interpret liquidityNet as the opposite sign
                    // safe because liquidityNet cannot be type(int128).min
                    if (zeroForOne) liquidityNet = -liquidityNet;
                    state.liquidity = liquidityNet < 0
                        ? state.liquidity - uint128(-liquidityNet)
                        : state.liquidity + uint128(liquidityNet);
                }

                state.tick = zeroForOne ? step.tickNext - 1 : step.tickNext;
            } else if (state.sqrtPriceX96 != step.sqrtPriceStartX96) {
                // recompute unless we're on a lower tick boundary (i.e. already transitioned ticks), and haven't moved
                state.tick = TickMath.getTickAtSqrtRatio(state.sqrtPriceX96);
            }
        }

        (amount0, amount1) = zeroForOne == exactInput
            ? (
                amountSpecified - state.amountSpecifiedRemaining,
                state.amountCalculated
            )
            : (
                state.amountCalculated,
                amountSpecified - state.amountSpecifiedRemaining
            );
    }

    /// @notice Overloads simulate swap to prevent passing a cache input
    /// @param v3Pool uniswap v3 pool address
    /// @param zeroForOne direction of swap, true means swap zero for one
    /// @param amountSpecified amount to swap in/out
    /// @param sqrtPriceLimitX96 the maximum price to swap to, if this price is reached, then the swap is stopped partially
    /// @return amount0 token0 amount
    /// @return amount1 token1 amount
    /// @return state swap state at the end of the swap
    /// @return cache swap cache populated with values, can be used for subsequent simulations
    function simulateSwap(
        IUniswapV3Pool v3Pool,
        bool zeroForOne,
        int256 amountSpecified,
        uint160 sqrtPriceLimitX96
    )
        public
        view
        returns (
            int256 amount0,
            int256 amount1,
            UniswapHelperViews.State memory state,
            UniswapHelperViews.Cache memory cache
        )
    {
        (amount0, amount1, state) = simulateSwap(
            v3Pool,
            zeroForOne,
            amountSpecified,
            sqrtPriceLimitX96,
            cache
        );
    }

    struct feesEarnedParams {
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
    /// @param lower Lower tick information from pool
    /// @param upper Upper tick information from pool
    function getFeesEarned(
        feesEarnedParams memory _feesEarnedParams,
        IUniswapV3Pool.TickInfo memory lower,
        IUniswapV3Pool.TickInfo memory upper
    ) internal pure returns (uint128 tokensOwed0, uint128 tokensOwed1) {
        uint256 feeGrowthBelow0X128;
        uint256 feeGrowthBelow1X128;
        if (_feesEarnedParams.tickCurrent >= _feesEarnedParams.tickLower) {
            feeGrowthBelow0X128 = lower.feeGrowthOutside0X128;
            feeGrowthBelow1X128 = lower.feeGrowthOutside1X128;
        } else {
            feeGrowthBelow0X128 =
                _feesEarnedParams.feeGrowthGlobal0X128 -
                lower.feeGrowthOutside0X128;
            feeGrowthBelow1X128 =
                _feesEarnedParams.feeGrowthGlobal1X128 -
                lower.feeGrowthOutside1X128;
        }

        // calculate fee growth above
        uint256 feeGrowthAbove0X128;
        uint256 feeGrowthAbove1X128;
        if (_feesEarnedParams.tickCurrent < _feesEarnedParams.tickUpper) {
            feeGrowthAbove0X128 = upper.feeGrowthOutside0X128;
            feeGrowthAbove1X128 = upper.feeGrowthOutside1X128;
        } else {
            feeGrowthAbove0X128 =
                _feesEarnedParams.feeGrowthGlobal0X128 -
                upper.feeGrowthOutside0X128;
            feeGrowthAbove1X128 =
                _feesEarnedParams.feeGrowthGlobal1X128 -
                upper.feeGrowthOutside1X128;
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

    function getRecenteringAmounts(
        uint160 currentPrice,
        uint160 lowTickPrice,
        uint160 highTickPrice
    ) external pure returns(uint256 _amount0, uint256 _amount1) {
        uint128 _liquidity = LiquidityAmounts.getLiquidityForAmounts(
            currentPrice, 
            lowTickPrice, 
            highTickPrice,
            PRECISION,
            PRECISION
            );
        (_amount0, _amount1) = LiquidityAmounts.getAmountsForLiquidity(
            currentPrice, 
            lowTickPrice, 
            highTickPrice,
            _liquidity
            );

        if(_amount0 > _amount1) {
            uint256 _toSwap = PRECISION - _amount1;
            uint256 _ratio = PRECISION * PRECISION / _amount1;
            uint256 _swapTo0 = _ratio * PRECISION / (_ratio + PRECISION) * _toSwap / PRECISION;
            _amount0 = _amount0 + _swapTo0;
            _amount1 = _amount1 + _toSwap - _swapTo0;
        } else {
            uint256 _toSwap = PRECISION - _amount0;
            uint256 _ratio = PRECISION * PRECISION / _amount0;
            uint256 _swapTo1 = _ratio * PRECISION / (_ratio + PRECISION) * _toSwap / PRECISION;
            _amount1 = _amount1 + _swapTo1;
            _amount0 = _amount0 + _toSwap - _swapTo1;
        }
    }

    function getSqrtRatioAtTick(int24 tick)
        external
        pure
        returns (uint160 sqrtPriceX96)
    {
        return TickMath.getSqrtRatioAtTick(tick);
    }
}
