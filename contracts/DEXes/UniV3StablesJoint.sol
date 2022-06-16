// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

// Import necessary libraries and interfaces:
// NoHedgeJoint to inherit from
import "../Hedges/NoHedgeJoint.sol";
// Uni V3 pool functionality
import {IUniswapV3Pool} from "@uniswap/contracts/interfaces/IUniswapV3Pool.sol";
// CRV pool functionalities for swaps and quotes
import {ICRVPool} from "../../interfaces/CRV/ICRVPool.sol";
// Helper functions from Uni v3
import {UniswapHelperViews} from "../libraries/UniswapHelperViews.sol";
// Liquidity calculations
import {LiquidityAmounts} from "../libraries/LiquidityAmounts.sol";
// Pool tick calculations
import {TickMath} from "../libraries/TickMath.sol";
// Safe casting and math
import {SafeCast} from "../libraries/SafeCast.sol";
import {FullMath} from "../libraries/FullMath.sol";
import {FixedPoint128} from "../libraries/FixedPoint128.sol";

contract UniV3StablesJoint is NoHedgeJoint {
    using SafeERC20 for IERC20;
    using SafeCast for uint256;
    
    // Used for cloning, will automatically be set to false for other clones
    bool public isOriginal = true;
    // lower tick of the current LP position
    int24 public minTick;
    // upper tick of the current LP position
    int24 public maxTick;
    // # of ticks to go up&down from current price to open LP position
    uint24 public ticksFromCurrent;
    // boolean variable deciding wether to swap in the uni v3 pool or using CRV
    // this can make sense if the pool is unbalanced and price is far from CRV or if the 
    // liquidity remaining in the pool is not enough for the rebalancing swap the strategy needs
    // to perform as the swap function from the uniV3 pool uses a while loop that would get stuck 
    // until we reach gas limit
    bool public useCRVPool;
    // CRV pool to use in case of useCRVPool = true
    address public crvPool;

    /// @dev The minimum value that can be returned from #getSqrtRatioAtTick. Equivalent to getSqrtRatioAtTick(MIN_TICK)
    uint160 internal constant MIN_SQRT_RATIO = 4295128739;
    /// @dev The maximum value that can be returned from #getSqrtRatioAtTick. Equivalent to getSqrtRatioAtTick(MAX_TICK)
    uint160 internal constant MAX_SQRT_RATIO =
        1461446703485210103287273052203988822378723970342;

    /*
     * @notice
     *  Constructor, only called during original deploy
     * @param _providerA, provider strategy of tokenA
     * @param _providerB, provider strategy of tokenB
     * @param _referenceToken, token to use as reference, for pricing oracles and paying hedging costs (if any)
     * @param _pool, Uni V3 pool to LP
     * @param _ticksFromCurrent, # of ticks up & down to provide liquidity into
     */
    constructor(
        address _providerA,
        address _providerB,
        address _referenceToken,
        address _pool,
        uint24 _ticksFromCurrent
    ) NoHedgeJoint(_providerA, _providerB, _referenceToken, _pool) {
        _initializeUniV3StablesJoint(_ticksFromCurrent);
    }

    /*
     * @notice
     *  Constructor equivalent for clones, initializing the joint and the specifics of UniV3StablesJoint
     * @param _providerA, provider strategy of tokenA
     * @param _providerB, provider strategy of tokenB
     * @param _referenceToken, token to use as reference, for pricing oracles and paying hedging costs (if any)
     * @param _pool, Uni V3 pool to LP
     * @param _ticksFromCurrent, # of ticks up & down to provide liquidity into
     */
    function initialize(
        address _providerA,
        address _providerB,
        address _referenceToken,
        address _pool,
        uint24 _ticksFromCurrent
    ) external {
        _initialize(_providerA, _providerB, _referenceToken, _pool);
        _initializeUniV3StablesJoint(_ticksFromCurrent);
    }

    /*
     * @notice
     *  Initialize UniV3StablesJoint specifics
     * @param _ticksFromCurrent, # of ticks up & down to provide liquidity into
     */
    function _initializeUniV3StablesJoint(uint24 _ticksFromCurrent) internal {
        ticksFromCurrent = _ticksFromCurrent;
        // The reward tokens are the tokens provided to the pool
        rewardTokens = new address[](2);
        rewardTokens[0] = tokenA;
        rewardTokens[1] = tokenB;
        // by default use uni pool to swap as it has lower fees
        useCRVPool = false;
        // Initialize CRV pool to 3pool
        crvPool = address(0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7);
    }

    event Cloned(address indexed clone);

    /*
     * @notice
     *  Cloning function to migrate/ deploy to other pools
     * @param _providerA, provider strategy of tokenA
     * @param _providerB, provider strategy of tokenB
     * @param _referenceToken, token to use as reference, for pricing oracles and paying hedging costs (if any)
     * @param _pool, Uni V3 pool to LP
     * @param _ticksFromCurrent, # of ticks up & down to provide liquidity into
     * @return newJoint, address of newly deployed joint
     */
    function cloneUniV3StablesJoint(
        address _providerA,
        address _providerB,
        address _referenceToken,
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

        UniV3StablesJoint(newJoint).initialize(
            _providerA,
            _providerB,
            _referenceToken,
            _pool,
            _ticksFromCurrent
        );

        emit Cloned(newJoint);
    }

    /*
     * @notice
     *  Function returning the name of the joint in the format "NoHedgeUniV3StablesJoint(USDC-DAI)"
     * @return name of the strategy
     */
    function name() external view override returns (string memory) {
        string memory ab = string(
            abi.encodePacked(
                IERC20Extended(address(tokenA)).symbol(),
                "-",
                IERC20Extended(address(tokenB)).symbol()
            )
        );

        return string(abi.encodePacked("NoHedgeUniV3StablesJoint(", ab, ")"));
    }

    /*
     * @notice
     *  Function returning the liquidity amount of the LP position
     * @return liquidity from positionInfo
     */
    function balanceOfPool() public view override returns (uint256 liquidity) {
        (liquidity,,,,) = _positionInfo();
    }

    /*
     * @notice
     *  Function available for vault managers to set the boolean value deciding wether
     * to use the uni v3 pool for swaps or a CRV pool
     * @param newUseCRVPool, new boolean value to use
     */
    function setUseCRVPool(bool _useCRVPool) external onlyVaultManagers {
        useCRVPool = _useCRVPool;
    }

    /*
     * @notice
     *  Function available for vault managers to set the number of ticks on each side of 
     * current tick to provide liquidity to
     * @param newTicksFromCurrent, new value to use
     */
    function setTicksFromCurrent(uint24 _ticksFromCurrent) external onlyVaultManagers {
        ticksFromCurrent = _ticksFromCurrent;
    }

    /*
     * @notice
     *  Function available for vault managers to set min & max values of the position. If,
     * for any reason the ticks are not the value they should be, we always have the option 
     * to re-set them back to the necessary value using the force parameter
     * @param _minTick, lower limit of position
     * @param _minTick, lower limit of position
     * @param forceChange, force parameter to ensure this function is not called randomly
     */
    function setTicksManually(int24 _minTick, int24 _maxTick, bool forceChange) external onlyVaultManagers {
        if ((investedA > 0 || investedB > 0) && !forceChange) {
            revert();
        }
        minTick = _minTick;
        maxTick = _maxTick;
    }

    /*
     * @notice
     *  Function returning the current balance of each token in the LP position taking
     * the new level of reserves into account
     * @return _balanceA, balance of tokenA in the LP position
     * @return _balanceB, balance of tokenB in the LP position
     */
    function balanceOfTokensInLP()
        public
        view
        override
        returns (uint256 _balanceA, uint256 _balanceB)
    {
        // Get the current pool status
        (uint160 sqrtPriceX96,,,,,,) = IUniswapV3Pool(pool).slot0();
        // Get the current position status
        (uint128 liquidity,,,,) = _positionInfo();

        // Use Uniswap libraries to calculate the token0 and token1 balances for the 
        // provided ticks and liquidity amount
        (uint256 amount0, uint256 amount1) = LiquidityAmounts
            .getAmountsForLiquidity(
                sqrtPriceX96,
                TickMath.getSqrtRatioAtTick(minTick),
                TickMath.getSqrtRatioAtTick(maxTick),
                liquidity
            );
        // uniswap orders token0 and token1 based on alphabetical order
        return tokenA < tokenB ? (amount0, amount1) : (amount1, amount0);
    }

    /*
     * @notice
     *  Function returning the amount of rewards earned until now - unclaimed
     * @return uint256 array of tokenA and tokenB earned as rewards
     */
    function pendingRewards() public view override returns (uint256[] memory) {
        // Initialize the array to same length as reward tokens
        uint256[] memory _amountPending = new uint256[](rewardTokens.length);

        // Get LP position info
        (uint128 liquidity,
        uint256 feeGrowthInside0LastX128,
        uint256 feeGrowthInside1LastX128,
        uint128 tokensOwed0,
        uint128 tokensOwed1) = _positionInfo();

        // Initialize to the current status of owed tokens
        (_amountPending[0], _amountPending[1]) = tokenA < tokenB
            ? (tokensOwed0, tokensOwed1)
            : (tokensOwed1, tokensOwed0);

        // Gas savings
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        int24 _minTick = minTick;
        int24 _maxTick = maxTick;

        // Use Uniswap views library to calculate the fees earned in tokenA and tokenB based
        // on current status of the pool and provided position
        (,int24 tick,,,,,) = _pool.slot0();
        (tokensOwed0, tokensOwed1) = UniswapHelperViews.getFeesEarned(
            UniswapHelperViews.feesEarnedParams(
                pool,
                liquidity,
                tick,
                _minTick,
                _maxTick,
                _pool.feeGrowthGlobal0X128(),
                _pool.feeGrowthGlobal1X128(),
                feeGrowthInside0LastX128,
                feeGrowthInside1LastX128
            )
        );

        // Reorder to make sure amounts are added correctly
        if (tokenA < tokenB) {
            _amountPending[0] += tokensOwed0;
            _amountPending[1] += tokensOwed1;
        } else {
            _amountPending[1] += tokensOwed0;
            _amountPending[0] += tokensOwed1;
        }

        return _amountPending;
    }

    /*
     * @notice
     *  Function called by the uniswap pool when minting the LP position (providing liquidity),
     * instead of approving and sending the tokens, uniV3 calls the callback imoplementation
     * on the caller contract
     * @param amount0Owed, amount of token0 to send
     * @param amount1Owed, amount of token1 to send
     * @param data, additional calldata
     */
    function uniswapV3MintCallback(
        uint256 amount0Owed,
        uint256 amount1Owed,
        bytes calldata data
    ) external {
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        // Only the pool can use this function
        require(msg.sender == address(_pool)); // dev: callback only called by pool
        // Send the required funds to the pool
        IERC20(_pool.token0()).safeTransfer(address(_pool), amount0Owed);
        IERC20(_pool.token1()).safeTransfer(address(_pool), amount1Owed);
    }

    /*
     * @notice
     *  Function called by the uniswap pool when swapping,
     * instead of approving and sending the tokens, uniV3 calls the callback imoplementation
     * on the caller contract
     * @param amount0Delta, amount of token0 to send (if any)
     * @param amount1Delta, amount of token1 to send (if any)
     * @param data, additional calldata
     */
    function uniswapV3SwapCallback(
        int256 amount0Delta,
        int256 amount1Delta,
        bytes calldata data
    ) external {
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        // Only the pool can use this function
        require(msg.sender == address(_pool)); // dev: callback only called by pool


        uint256 amountIn;
        address tokenIn;

        // Send the required funds to the pool
        if (amount0Delta > 0) {
            amountIn = uint256(amount0Delta);
            tokenIn = _pool.token0();
        } else {
            amountIn = uint256(amount1Delta);
            tokenIn = _pool.token1();
        }

        IERC20(tokenIn).safeTransfer(address(_pool), amountIn);
    }

    /*
     * @notice
     *  Function used internally to collect the accrued fees by burn 0 of the LP position
     * and collecting the owed tokens (only fees as no LP has been burnt)
     * @return balance of tokens in the LP (invested amounts)
     */
    function getReward() internal override {
        _burnAndCollect(0, minTick, maxTick);
    }

    /*
     * @notice
     *  Function used internally to open the LP position in the uni v3 pool: 
     *      - calculates the ticks to provide liquidity into
     *      - calculates the liquidity amount to provide based on the ticks 
     *      and amounts to invest
     *      - calls the mint function in the uni v3 pool
     * @return balance of tokens in the LP (invested amounts)
     */
    function createLP() internal override returns (uint256, uint256) {
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        // Get the current state of the pool
        (uint160 sqrtPriceX96, int24 tick,,,,,) = _pool.slot0();
        // Space between ticks for this pool
        int24 _tickSpacing = _pool.tickSpacing();
        // Current tick must be referenced as a multiple of tickSpacing
        int24 _currentTick = (tick / _tickSpacing) * _tickSpacing;
        // Gas savings for # of ticks to LP
        int24 _ticksFromCurrent = int24(ticksFromCurrent);
        // Minimum tick to enter
        int24 _minTick = _currentTick - (_tickSpacing * _ticksFromCurrent);
        // Maximum tick to enter
        int24 _maxTick = _currentTick + (_tickSpacing * (_ticksFromCurrent + 1));

        // Set the state variables
        minTick = _minTick;
        maxTick = _maxTick;

        uint256 amount0;
        uint256 amount1;

        // MAke sure tokens are in order
        if (tokenA < tokenB) {
            amount0 = balanceOfA();
            amount1 = balanceOfB();
        } else {
            amount0 = balanceOfB();
            amount1 = balanceOfA();
        }

        // Calculate the amount of liquidity the joint can provided based on current situation
        // and amount of tokens available
        uint128 liquidityAmount = LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            TickMath.getSqrtRatioAtTick(_minTick),
            TickMath.getSqrtRatioAtTick(_maxTick),
            amount0,
            amount1
        );

        // Mint the LP position - we are not yet in the LP, needs to go through the mint
        // callback first
        _pool.mint(address(this), _minTick, _maxTick, liquidityAmount, "");

        // After executing the mint callback, calculate the invested amounts
        return balanceOfTokensInLP();
    }

    /*
     * @notice
     *  Function used internally to close the LP position in the uni v3 pool: 
     *      - burns the LP liquidity specified amount
     *      - collects all pending rewards
     *      - re-sets the active position min and max tick to 0
     * @param amount, amount of liquidity to burn
     */
    function burnLP(uint256 amount) internal override {
        _burnAndCollect(amount, minTick, maxTick);
        // If entire position is closed, re-set the min and max ticks
        (uint128 liquidity,,,,) = _positionInfo();
        if (liquidity == 0){
            minTick = 0;
            maxTick = 0;
        }
    }

    /*
     * @notice
     *  Function available to vault managers to burn the LP manually, if for any reason
     * the ticks have been set to 0 (or any different value from the original LP), we make 
     * sure we can always get out of the position
     * This function can be used to only collect fees by passing a 0 amount to burn
     * @param _amount, amount of liquidity to burn
     * @param _minTick, lower limit of position
     * @param _maxTick, upper limit of position
     */
    function burnLPManually(
            uint256 _amount,
            int24 _minTick,
            int24 _maxTick
            ) external onlyVaultManagers {
        _burnAndCollect(_amount, _minTick, _maxTick);
    }

    /*
     * @notice
     *  Function available internally to burn the LP amount specified, for position
     * defined by minTick and maxTick specified and collect the owed tokens
     * @param _amount, amount of liquidity to burn
     * @param _minTick, lower limit of position
     * @param _maxTick, upper limit of position
     */
    function _burnAndCollect(
        uint256 _amount,
        int24 _minTick,
        int24 _maxTick
    ) internal {
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        _pool.burn(_minTick, _maxTick, uint128(_amount));
        _pool.collect(
            address(this),
            _minTick,
            _maxTick,
            type(uint128).max,
            type(uint128).max
        );
    }

    /*
     * @notice
     *  Function used internally to swap tokens during rebalancing. Depending on the useCRVPool
     * state variable it will either use the uni v3 pool to swap or a CRV pool specified in 
     * crvPool state variable
     * @param _tokenFrom, adress of token to swap from
     * @param _tokenTo, address of token to swap to
     * @param _amountIn, amount of _tokenIn to swap for _tokenTo
     * @return swapped amount
     */
    function swap(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal override returns (uint256) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        if (useCRVPool) {
            // Do NOT use uni pool use CRV pool
            ICRVPool _pool = ICRVPool(crvPool);
        
            // Allow necessary amount for CRV pool
            _checkAllowance(address(_pool), IERC20(_tokenFrom), _amountIn);
            uint256 prevBalance = IERC20(_tokenTo).balanceOf(address(this));
            // Perform swap
            _pool.exchange(
                _getCRVPoolIndex(_tokenFrom, _pool), 
                _getCRVPoolIndex(_tokenTo, _pool),
                _amountIn, 
                0
            );
            // Revoke allowance
            IERC20(_tokenFrom).safeApprove(address(_pool), 0);
            return (IERC20(_tokenTo).balanceOf(address(this)) - prevBalance);
        } else {
            // Use uni v3 pool to swap
            // Order of swap
            bool zeroForOne = _tokenFrom < _tokenTo;

            // Use swap function of uni v3 pool, will use the implemented swap callback to 
            // receive the corresponding tokens
            (int256 _amount0, int256 _amount1) = IUniswapV3Pool(pool).swap(
                // recipient
                address(this),
                // Order of swap
                zeroForOne,
                // amountSpecified
                _amountIn.toInt256(),
                // Price limit
                zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1,
                // additonal calldata
                ""
            );

            // Ensure amounts are returned in right order and sign (uni returns negative numbers)
            return zeroForOne ? uint256(-_amount1) : uint256(-_amount0);
        }
        
    }

    /*
     * @notice
     *  Function used internally to quote a potential rebalancing swap without actually 
     * executing it. Same as the swap function, will simulate the trade either on the uni v3
     * pool or CRV pool based on useCRVPool
     * @param _tokenFrom, adress of token to swap from
     * @param _tokenTo, address of token to swap to
     * @param _amountIn, amount of _tokenIn to swap for _tokenTo
     * @return simulated swapped amount
     */
    function quote(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal view override returns (uint256) {
        require(_tokenTo == tokenA || _tokenTo == tokenB); // dev: must be a or b
        require(_tokenFrom == tokenA || _tokenFrom == tokenB); // dev: must be a or b
        if(!useCRVPool){
            // Use uni v3 pool to swap
            // Order of swap
            bool zeroForOne = _tokenFrom < _tokenTo;

            // Use the uniswap helper view to simulate the swap in the uni v3 pool
            (int256 _amount0, int256 _amount1) = UniswapHelperViews.simulateSwap(
                // pool to use
                pool,
                // order of swap
                zeroForOne,
                // amountSpecified
                _amountIn.toInt256(),
                // price limit
                zeroForOne ? MIN_SQRT_RATIO + 1 : MAX_SQRT_RATIO - 1
            );

            // Ensure amounts are returned in right order and sign (uni returns negative numbers)
            return zeroForOne ? uint256(-_amount1) : uint256(-_amount0);
        } else {
            // Do NOT use uni pool use CRV pool
            
            ICRVPool _pool = ICRVPool(crvPool);

            // Call the quote function in CRV pool
            return _pool.get_dy(
                _getCRVPoolIndex(_tokenFrom, _pool), 
                _getCRVPoolIndex(_tokenTo, _pool), 
                _amountIn
            );
        }
        
    }

    /*
     * @notice
     *  Function used internally to retrieve the CRV index for a token in a CRV pool, for example
     * 3Pool uses:
     * - 0 is DAI
     * - 1 is USDC
     * - 2 is USDT
     * @return in128 containing the token's pool index
     */
    function _getCRVPoolIndex(address _token, ICRVPool _pool) internal view returns(int128) {
        if(_pool.coins(0) == _token) {
                return int128(0);
            } else if (_pool.coins(1) == _token) {
                return int128(1);
            } else if (_pool.coins(2) == _token) {
                return int128(2);
            } else {
                revert();
            }
    }

    /*
     * @notice
     *  Function used internally to retrieve the details of the joint's LP position:
     * - the amount of liquidity owned by this position
     * - fee growth per unit of liquidity as of the last update to liquidity or fees owed
     * - the fees owed to the position owner in token0/token1
     * @return PositionInfo struct containing the position details
     */
    function _positionInfo()
        private
        view
        returns (
            uint128 liquidity,
            uint256 feeGrowthInside0LastX128,
            uint256 feeGrowthInside1LastX128,
            uint128 tokensOwed0,
            uint128 tokensOwed1
        )
    {
        bytes32 key = keccak256(
            abi.encodePacked(address(this), minTick, maxTick)
        );
        return IUniswapV3Pool(pool).positions(key);
    }

    /*
     * @notice
     *  Function used by governance to swap tokens manually if needed, can be used when closing 
     * the LP position manually and need some re-balancing before sending funds back to the 
     * providers
     * @param swapPath, path of addresses to swap, should be 2 and always tokenA <> tokenB
     * @param swapInAmount, amount of swapPath[0] to swap for swapPath[1]
     * @param minOutAmount, minimum amount of want out
     * @return swapped amount
     */
    function swapTokenForTokenManually(
        address[] memory swapPath,
        uint256 swapInAmount,
        uint256 minOutAmount
    ) external onlyGovernance override returns (uint256) {
        address _tokenA = tokenA;
        address _tokenB = tokenB;
        require(swapPath.length == 2);
        require(swapPath[0] == _tokenA || swapPath[1] == _tokenA);
        require(swapPath[0] == _tokenB || swapPath[1] == _tokenB);
        return swap(
            swapPath[0], 
            swapPath[1], 
            swapInAmount
            );
    }

    /*
     * @notice
     *  Function used by keepers to assess whether to harvest the joint and compound generated
     * fees into the existing position, checks whether both pending fee amounts (tokenA and B)
     * are greater than minRewardToHarvest
     * @param callCost, call cost parameter
     * @return bool amount assessing whether to harvest or not
     */
    function harvestTrigger(uint256 callCost) external view override returns (bool) {

        uint256 _minRewardToHarvest = minRewardToHarvest;
        if (_minRewardToHarvest == 0) {
            return false;
        }

        uint256[] memory _pendingRewards = pendingRewards();

        if (_pendingRewards[0] >= _minRewardToHarvest * (10**IERC20Extended(rewardTokens[0]).decimals()) / RATIO_PRECISION && 
            _pendingRewards[1] >= _minRewardToHarvest * (10**IERC20Extended(rewardTokens[1]).decimals()) / RATIO_PRECISION
        ) {
            return true;
        }

    }

    /*
     * @notice
     *  Function used by harvest trigger in the providers to assess whether to harvest it as
     * the joint may have gone out of bounds. If debt ratio is kept in the vaults, the joint
     * re-centers, if debt ratio is 0, the joint is simpley closed and funds are sent back
     * to each provider
     * @return bool amount assessing whether to end the epoch or not
     */
    function shouldEndEpoch() external view override returns (bool) {
        (,int24 _tick,,,,,) = IUniswapV3Pool(pool).slot0();
        (uint128 liquidity,,,,) = _positionInfo();
        if((_tick < minTick || _tick >= maxTick) && (liquidity > 0)) {
            return true;
        }
    }

    /*
     * @notice
     *  Function used by keepers to compound the generated feed into the existing position
     * in the joint. There may be some funds not used in the position and left idle in the 
     * joint
     */
    function harvest() external override onlyKeepers {
        getReward();

        uint256 amount0;
        uint256 amount1;

        // Make sure tokens are in order
        if (tokenA < tokenB) {
            amount0 = balanceOfA();
            amount1 = balanceOfB();
        } else {
            amount0 = balanceOfB();
            amount1 = balanceOfA();
        }

        // Minimum tick to enter
        int24 _minTick = minTick;
        // Maximum tick to enter
        int24 _maxTick = maxTick;

        // Calculate the amount of liquidity the joint can provided based on current situation
        // and amount of tokens available
        IUniswapV3Pool _pool = IUniswapV3Pool(pool);
        (uint160 sqrtPriceX96,,,,,,) = _pool.slot0();
        uint128 liquidityAmount = LiquidityAmounts.getLiquidityForAmounts(
            sqrtPriceX96,
            TickMath.getSqrtRatioAtTick(_minTick),
            TickMath.getSqrtRatioAtTick(_maxTick),
            amount0,
            amount1
        );

        // Mint the LP position - we are not yet in the LP, needs to go through the mint
        // callback first
        _pool.mint(address(this), _minTick, _maxTick, liquidityAmount, "");

    }
}
