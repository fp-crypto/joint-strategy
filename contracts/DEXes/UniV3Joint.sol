// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

import "../Hedges/NoHedgeJoint.sol";
import {IUniswapV3Pool} from "../../interfaces/uniswap/V3/IUniswapV3Pool.sol";
import {ICRVPool} from "../../interfaces/CRV/ICRVPool.sol";
import {UniswapHelperViews} from "../libraries/UniswapHelperViews.sol";
import {LiquidityAmounts} from "../libraries/LiquidityAmounts.sol";
import {TickMath} from "../libraries/TickMath.sol";
import {SafeCast} from "../libraries/SafeCast.sol";
import {FullMath} from "../libraries/FullMath.sol";
import {FixedPoint128} from "../libraries/FixedPoint128.sol";

contract UniV3Joint is NoHedgeJoint {
    using SafeERC20 for IERC20;
    using SafeCast for uint256;

    bool public isOriginal = true;
    int24 public minTick;
    int24 public maxTick;
    uint24 public ticksFromCurrent;
    bool public useUniswapPool;
    address public crvPool;

    /// @dev The minimum value that can be returned from #getSqrtRatioAtTick. Equivalent to getSqrtRatioAtTick(MIN_TICK)
    uint160 internal constant MIN_SQRT_RATIO = 4295128739;
    /// @dev The maximum value that can be returned from #getSqrtRatioAtTick. Equivalent to getSqrtRatioAtTick(MAX_TICK)
    uint160 internal constant MAX_SQRT_RATIO =
        1461446703485210103287273052203988822378723970342;

    constructor(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool,
        uint24 _ticksFromCurrent
    ) public NoHedgeJoint(_providerA, _providerB, _weth, _pool) {
        _initalizeUniV3Joint(_ticksFromCurrent);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool,
        uint24 _ticksFromCurrent
    ) external {
        _initialize(_providerA, _providerB, _weth, _pool);
        _initalizeUniV3Joint(_ticksFromCurrent);
    }

    function _initalizeUniV3Joint(uint24 _ticksFromCurrent) internal {
        ticksFromCurrent = _ticksFromCurrent;
        rewardTokens = new address[](2);
        rewardTokens[0] = tokenA;
        rewardTokens[1] = tokenB;
        useUniswapPool = true;
        // Initialize CRV pool to 3pool
        crvPool = address(0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7);
    }

    event Cloned(address indexed clone);

    function cloneUniV3Joint(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool,
        uint24 _ticksFromCurrent
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

        UniV3Joint(newJoint).initialize(
            _providerA,
            _providerB,
            _weth,
            _pool,
            _ticksFromCurrent
        );

        emit Cloned(newJoint);
    }

    function name() external view override returns (string memory) {
        string memory ab = string(
            abi.encodePacked(
                IERC20Extended(address(tokenA)).symbol(),
                "-",
                IERC20Extended(address(tokenB)).symbol()
            )
        );

        return string(abi.encodePacked("NoHedgeUniV3Joint(", ab, ")"));
    }

    function balanceOfPool() public view override returns (uint256) {
        IUniswapV3Pool.PositionInfo memory positionInfo = _positionInfo();
        return positionInfo.liquidity;
    }

    function setCRVPool(address newPool) external onlyVaultManagers {
        crvPool = newPool;
    }

    function setUseUniswapPool(bool newUseUniswapPool) external onlyVaultManagers {
        useUniswapPool = newUseUniswapPool;
    }

    function balanceOfTokensInLP()
        public
        view
        override
        returns (uint256 _balanceA, uint256 _balanceB)
    {
        IUniswapV3Pool.Slot0 memory _slot0 = IUniswapV3Pool(pool).slot0();
        uint160 _sqrtPriceX96 = _slot0.sqrtPriceX96;
        IUniswapV3Pool.PositionInfo memory positionInfo = _positionInfo();
        uint128 _liquidity = positionInfo.liquidity;

        (uint256 amount0, uint256 amount1) = LiquidityAmounts
            .getAmountsForLiquidity(
                _sqrtPriceX96,
                TickMath.getSqrtRatioAtTick(minTick),
                TickMath.getSqrtRatioAtTick(maxTick),
                _liquidity
            );

        return tokenA < tokenB ? (amount0, amount1) : (amount1, amount0);
    }

    function pendingRewards() public view override returns (uint256[] memory) {
        uint256[] memory _amountPending = new uint256[](rewardTokens.length);

        IUniswapV3Pool.PositionInfo memory positionInfo = _positionInfo();

        (_amountPending[0], _amountPending[1]) = tokenA < tokenB
            ? (positionInfo.tokensOwed0, positionInfo.tokensOwed1)
            : (positionInfo.tokensOwed1, positionInfo.tokensOwed0);

        IUniswapV3Pool _pool = IUniswapV3Pool(pool);

        uint256 feeGrowthInside0LastX128 = positionInfo
            .feeGrowthInside0LastX128;
        uint256 feeGrowthInside1LastX128 = positionInfo
            .feeGrowthInside1LastX128;

        (uint128 tokensOwed0, uint128 tokensOwed1) = UniswapHelperViews.getFeesEarned(
            UniswapHelperViews.feesEarnedParams(
                positionInfo.liquidity,
                _pool.slot0().tick,
                minTick,
                maxTick,
                _pool.feeGrowthGlobal0X128(),
                _pool.feeGrowthGlobal1X128(),
                feeGrowthInside0LastX128,
                feeGrowthInside1LastX128
            ),
            _pool.ticks(minTick),
            _pool.ticks(maxTick)
        );

        if (tokenA < tokenB) {
            _amountPending[0] += tokensOwed0;
            _amountPending[1] += tokensOwed1;
        } else {
            _amountPending[1] += tokensOwed0;
            _amountPending[0] += tokensOwed1;
        }

        return _amountPending;
    }

    function uniswapV3MintCallback(
        uint256 amount0Owed,
        uint256 amount1Owed,
        bytes calldata data
    ) external {
        require(msg.sender == pool); // dev: callback only called by pool

        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        IERC20(_pool.token0()).safeTransfer(address(_pool), amount0Owed);
        IERC20(_pool.token1()).safeTransfer(address(_pool), amount1Owed);
    }

    function uniswapV3SwapCallback(
        int256 amount0Delta,
        int256 amount1Delta,
        bytes calldata data
    ) external {
        require(msg.sender == address(pool)); // dev: callback only called by pool

        IUniswapV3Pool _pool = IUniswapV3Pool(pool);

        uint256 amountIn;
        address tokenIn;

        if (amount0Delta > 0) {
            amountIn = uint256(amount0Delta);
            tokenIn = _pool.token0();
        } else {
            amountIn = uint256(amount1Delta);
            tokenIn = _pool.token1();
        }

        IERC20(tokenIn).safeTransfer(address(_pool), amountIn);
    }

    function getReward() internal override {
        IUniswapV3Pool(pool).collect(
            address(this),
            minTick,
            maxTick,
            type(uint128).max,
            type(uint128).max
        );
    }

    function createLP() internal override returns (uint256, uint256) {
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        IUniswapV3Pool.Slot0 memory _slot0 = _pool.slot0();

        int24 _tickSpacing = _pool.tickSpacing();
        int24 _currentTick = (_slot0.tick / _tickSpacing) * _tickSpacing;
        int24 _ticksFromCurrent = int24(ticksFromCurrent);
        minTick = _currentTick - (_tickSpacing * _ticksFromCurrent);
        maxTick = _currentTick + (_tickSpacing * (_ticksFromCurrent + 1));

        uint160 sqrtPriceX96 = _slot0.sqrtPriceX96;
        uint160 sqrtRatioAX96 = TickMath.getSqrtRatioAtTick(minTick);
        uint160 sqrtRatioBX96 = TickMath.getSqrtRatioAtTick(maxTick);
        uint256 amount0;
        uint256 amount1;

        if (tokenA < tokenB) {
            amount0 = balanceOfA();
            amount1 = balanceOfB();
        } else {
            amount0 = balanceOfB();
            amount1 = balanceOfA();
        }

        uint128 liquidityAmount = LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            sqrtRatioAX96,
            sqrtRatioBX96,
            amount0,
            amount1
        );

        _pool.mint(address(this), minTick, maxTick, liquidityAmount, "");

        return balanceOfTokensInLP();
    }

    function burnLP(uint256 amount) internal override {
        IUniswapV3Pool(pool).burn(minTick, maxTick, uint128(amount));
        getReward();
        minTick = 0;
        maxTick = 0;
    }

    function swap(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal override returns (uint256) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        if (useUniswapPool) {
            bool zeroForOne = _tokenFrom < _tokenTo;

            (int256 _amount0, int256 _amount1) = IUniswapV3Pool(pool).swap(
                address(this), // address(0) might cause issues with some tokens
                zeroForOne,
                _amountIn.toInt256(),
                zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1,
                ""
            );

            return zeroForOne ? uint256(-_amount1) : uint256(-_amount0);
        } else {
            // Do NOT use uni pool use CRV 3pool
            // 3crv uses indexes:
            // 0 for DAI
            // 1 for USDC
            // 2 for USDT
            ICRVPool _pool = ICRVPool(crvPool);
            int128 indexTokenIn = (_pool.coins(1) == _tokenFrom) ? int128(1) : int128(2);
            int128 indexTokenOut = (indexTokenIn == 1) ? int128(2) : int128(1);
            _checkAllowance(address(_pool), IERC20(_tokenFrom), _amountIn);
            _pool.exchange(
                indexTokenIn, 
                indexTokenOut, 
                _amountIn, 
                0
            );
            IERC20(_tokenFrom).safeApprove(address(_pool), 0);

        }
        
    }

    function quote(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal view override returns (uint256) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        if(useUniswapPool){
            bool zeroForOne = _tokenFrom < _tokenTo;

            (int256 _amount0, int256 _amount1, , ) = UniswapHelperViews.simulateSwap(
                IUniswapV3Pool(pool),
                zeroForOne,
                _amountIn.toInt256(),
                zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1
            );

            return zeroForOne ? uint256(-_amount1) : uint256(-_amount0);
        } else {
            // Do NOT use uni pool use CRV 3pool
            // 3crv uses indexes:
            // 0 for DAI
            // 1 for USDC
            // 2 for USDT
            ICRVPool _pool = ICRVPool(crvPool);
            int128 indexTokenIn = (_pool.coins(1) == _tokenFrom) ? int128(1) : int128(2);
            int128 indexTokenOut = (indexTokenIn == 1) ? int128(2) : int128(1);
            return _pool.get_dy(
                indexTokenIn, 
                indexTokenOut, 
                _amountIn
            );
        }
        
    }

    function _positionInfo()
        private
        view
        returns (IUniswapV3Pool.PositionInfo memory)
    {
        bytes32 key = keccak256(
            abi.encodePacked(address(this), minTick, maxTick)
        );
        return IUniswapV3Pool(pool).positions(key);
    }
}
