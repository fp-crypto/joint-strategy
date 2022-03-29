// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

import "../Hedges/NoHedgeJoint.sol";
import "../../interfaces/uni/IUniswapV3Pool.sol";

contract UniV3Joint is NoHedgeJoint {
    using SafeERC20 for IERC20;

    bool public isOriginal = true;
    int24 public minTick;
    int24 public maxTick;

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
        int24 _minTick,
        int24 _maxTick
    ) public NoHedgeJoint(_providerA, _providerB, _weth, _pool) {
        _initalizeUniV3Joint(_minTick, _maxTick);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool,
        int24 _minTick,
        int24 _maxTick
    ) external {
        _initialize(_providerA, _providerB, _weth, _pool);
        _initalizeUniV3Joint(_minTick, _maxTick);
    }

    function _initalizeUniV3Joint(int24 _minTick, int24 _maxTick) internal {
        minTick = _minTick;
        maxTick = _maxTick;
        rewardTokens = new address[](2);
        rewardTokens[0] = tokenA;
        rewardTokens[1] = tokenB;
    }

    event Cloned(address indexed clone);

    function cloneUniV3Joint(
        address _providerA,
        address _providerB,
        address _weth,
        address _pool,
        int24 _minTick,
        int24 _maxTick
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
            _minTick,
            _maxTick
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

        return string(abi.encodePacked("NoHedgeUniV3Joint(", ab, ")"));
    }

    function balanceOfPool() public view override returns (uint256) {
        IUniswapV3Pool.PositionInfo memory positionInfo = _positionInfo();
        return positionInfo.liquidity;
    }

    function balanceOfTokensInLP()
        public
        view
        override
        returns (uint256 _balanceA, uint256 _balanceB)
    {}

    function pendingReward(uint256 i)
        public
        view
        override
        returns (uint256 _amountPending)
    {
        IUniswapV3Pool.PositionInfo memory positionInfo = _positionInfo();

        if (i == 0) {
            _amountPending = tokenA == IUniswapV3Pool(pool).token0()
                ? positionInfo.tokensOwed0
                : positionInfo.tokensOwed1;
        } else if (i == 1) {
            _amountPending = tokenA == IUniswapV3Pool(pool).token0()
                ? positionInfo.tokensOwed1
                : positionInfo.tokensOwed0;
        }
    }

    function uniswapV3MintCallback(
        uint256 amount0Owed,
        uint256 amount1Owed,
        bytes calldata data
    ) external {
        require(msg.sender == pool); // dev: callback only called by pool

        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        address _token0 = _pool.token0();
        address _token1 = _pool.token1();

        if (_token0 == tokenA && _token1 == tokenB) {
            require(balanceOfA() >= amount0Owed);
            require(balanceOfB() >= amount1Owed);
        } else if (_pool.token0() == tokenB && _pool.token1() == tokenA) {
            require(balanceOfB() >= amount0Owed);
            require(balanceOfA() >= amount1Owed);
        } else {
            revert("TSNFH"); // dev: this should never happen
        }

        IERC20(_token0).safeTransfer(address(_pool), amount0Owed);
        IERC20(_token1).safeTransfer(address(_pool), amount1Owed);
    }

    function uniswapV3SwapCallback(
        int256 amount0Delta,
        int256 amount1Delta,
        bytes calldata data
    ) external {
        require(msg.sender == address(pool)); // dev: callback only called by pool

        (address tokenIn, address tokenOut, bool quote) =
            abi.decode(data, (address, address, bool));

        IUniswapV3Pool _pool = IUniswapV3Pool(pool);

        uint256 amountIn;
        uint256 amountOut;

        if (amount0Delta < 0) {
            require(tokenIn == _pool.token0());
            amountIn = uint256(-amount0Delta);
            amountOut = uint256(amount1Delta);
        } else {
            require(tokenIn == _pool.token1());
            amountIn = uint256(-amount1Delta);
            amountOut = uint256(amount0Delta);
        }

        if (quote) {
            revert(string(abi.encodePacked(amountOut)));
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

    function createLP()
        internal
        override
        returns (
            uint256,
            uint256,
            uint256
        )
    {
        return (0, 0, 0);
    }

    function burnLP(uint256 amount) internal override {
        IUniswapV3Pool(pool).burn(minTick, maxTick, uint128(amount));
    }

    function swap(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal override returns (uint256 _amountOut) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        require(_amountIn < 2**255); // dev: amountIn will fail cast to int256

        bool zeroForOne = _tokenFrom < _tokenTo;

        IUniswapV3Pool(pool).swap(
            address(this), // address(0) might cause issues with some tokens
            zeroForOne,
            int256(_amountIn),
            zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1,
            abi.encodePacked(_tokenFrom, _tokenTo, false)
        );
    }

    function quote(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal view override returns (uint256 _amountOut) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        require(_amountIn < 2**255); // dev: amountIn will fail cast to int256
    }

    function _positionInfo()
        private
        view
        returns (IUniswapV3Pool.PositionInfo memory)
    {
        bytes32 key =
            keccak256(abi.encodePacked(address(this), minTick, maxTick));
        return IUniswapV3Pool(pool).positions(key);
    }
}
