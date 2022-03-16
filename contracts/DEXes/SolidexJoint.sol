// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import "../ySwapper.sol";
import "../Hedges/NoHedgeJoint.sol";
import "../../interfaces/ISolidex.sol";
import "../../interfaces/ISolidRouter.sol";

interface ISolidlyPair is IUniswapV2Pair {
    function getAmountOut(uint256 amountIn, address tokenIn)
        external
        view
        returns (uint256);
}

contract SolidexJoint is NoHedgeJoint {
    ISolidex public solidex;
    bool public stable;
    bool public dontWithdraw;

    bool public isOriginal = true;

    address public constant SEX = 0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7;
    address public constant SOLID_SEX =
        0x888EF71766ca594DED1F0FA3AE64eD2941740A20;

    constructor(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex,
        bool _stable
    ) public NoHedgeJoint(_providerA, _providerB, _router, _weth, _reward) {
        _initalizeSolidexJoint(_solidex, _stable);
    }

    function initialize(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex,
        bool _stable
    ) external {
        _initialize(_providerA, _providerB, _router, _weth, _reward);
        _initalizeSolidexJoint(_solidex, _stable);
    }

    function _initalizeSolidexJoint(address _solidex, bool _stable) internal {
        solidex = ISolidex(_solidex);
        stable = _stable;
        pair = IUniswapV2Pair(getPair());
        IERC20(address(pair)).approve(_solidex, type(uint256).max);
        IERC20(address(pair)).approve(address(router), type(uint256).max);
    }

    event Cloned(address indexed clone);

    function cloneSolidexJoint(
        address _providerA,
        address _providerB,
        address _router,
        address _weth,
        address _reward,
        address _solidex,
        bool _stable
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

        SolidexJoint(newJoint).initialize(
            _providerA,
            _providerB,
            _router,
            _weth,
            _reward,
            _solidex,
            _stable
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

        return string(abi.encodePacked("NoHedgeSolidexJoint(", ab, ")"));
    }

    function balanceOfStake() public view override returns (uint256) {
        return solidex.userBalances(address(this), address(pair));
    }

    function pendingReward() public view override returns (uint256) {
        address[] memory pairs = new address[](1);
        pairs[0] = address(pair);
        ISolidex.Amounts[] memory pendings =
            solidex.pendingRewards(address(this), pairs);

        uint256 pendingSEX = pendings[0].sex;
        uint256 pendingSOLID = pendings[0].solid;

        ISolidRouter.route[] memory path = getTokenOutPathSolid(SEX, SOLID_SEX);
        pendingSOLID = pendingSOLID.add(
            ISolidRouter(router).getAmountsOut(pendingSEX, path)[1]
        );

        return pendingSOLID;
    }

    function getReward() internal override {
        address[] memory pairs = new address[](1);
        pairs[0] = address(pair);
        solidex.getReward(pairs);
    }

    function setDontWithdraw(bool _dontWithdraw) external onlyVaultManagers {
        dontWithdraw = _dontWithdraw;
    }

    function depositLP() internal override {
        if (balanceOfPair() > 0) {
            solidex.deposit(address(pair), balanceOfPair());
        }
    }

    function withdrawLP() internal override {
        uint256 stakeBalance = balanceOfStake();
        if (stakeBalance > 0 && !dontWithdraw) {
            getReward();
            solidex.withdraw(address(pair), stakeBalance);
        }
    }

    function claimRewardManually() external onlyVaultManagers {
        getReward();
    }

    function withdrawLPManually(uint256 amount) external onlyVaultManagers {
        solidex.withdraw(address(pair), amount);
    }

    // OVERRIDE to incorporate stableswap or volatileswap
    function createLP()
        internal
        override
        returns (
            uint256,
            uint256,
            uint256
        )
    {
        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        return
            ISolidRouter(router).addLiquidity(
                tokenA,
                tokenB,
                stable,
                balanceOfA()
                    .mul(RATIO_PRECISION.sub(getHedgeBudget(tokenA)))
                    .div(RATIO_PRECISION),
                balanceOfB()
                    .mul(RATIO_PRECISION.sub(getHedgeBudget(tokenB)))
                    .div(RATIO_PRECISION),
                0,
                0,
                address(this),
                now
            );
    }

    function _closePosition() internal override returns (uint256, uint256) {
        // Unstake LP from staking contract
        withdrawLP();

        // Close the hedge
        closeHedge();

        if (balanceOfPair() == 0) {
            return (0, 0);
        }

        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        ISolidRouter(router).removeLiquidity(
            tokenA,
            tokenB,
            stable,
            balanceOfPair(),
            0,
            0,
            address(this),
            now
        );

        return (balanceOfA(), balanceOfB());
    }

    function removeLiquidityManually(
        uint256 amount,
        uint256 expectedBalanceA,
        uint256 expectedBalanceB
    ) external override onlyVaultManagers {
        ISolidRouter(router).removeLiquidity(
            tokenA,
            tokenB,
            stable,
            amount,
            0,
            0,
            address(this),
            now
        );
        require(expectedBalanceA <= balanceOfA(), "!sandwidched");
        require(expectedBalanceB <= balanceOfB(), "!sandwidched");
    }

    function sellCapital(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal override returns (uint256 _amountOut) {
        uint256[] memory amounts =
            ISolidRouter(router).swapExactTokensForTokens(
                _amountIn,
                0,
                getTokenOutPathSolid(_tokenFrom, _tokenTo),
                address(this),
                now
            );
        _amountOut = amounts[amounts.length - 1];
    }

    function getTokenOutPathSolid(address _token_in, address _token_out)
        internal
        view
        returns (ISolidRouter.route[] memory _routes)
    {
        address[] memory _path;
        bool is_weth =
            _token_in == address(WETH) || _token_out == address(WETH);
        bool is_internal =
            (_token_in == tokenA && _token_out == tokenB) ||
                (_token_in == tokenB && _token_out == tokenA);
        _path = new address[](is_weth || is_internal ? 2 : 3);
        _path[0] = _token_in;
        if (is_weth || is_internal) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(WETH);
            _path[2] = _token_out;
        }

        uint256 pathLength = _path.length > 1 ? _path.length - 1 : 1;
        _routes = new ISolidRouter.route[](pathLength);
        for (uint256 i = 0; i < pathLength; i++) {
            bool isStable = is_internal ? stable : false;
            _routes[i] = ISolidRouter.route(_path[i], _path[i + 1], isStable);
        }
    }

    function swapReward(uint256 _rewardBal)
        internal
        override
        returns (address, uint256)
    {
        // WARNING: NOT SELLING REWARDS! !!!
        if (reward == tokenA || reward == tokenB || _rewardBal == 0) {
            return (reward, 0);
        }

        if (tokenA == WETH || tokenB == WETH) {
            return (WETH, 0);
        }

        // Assume that position has already been liquidated
        (uint256 ratioA, uint256 ratioB) =
            getRatios(balanceOfA(), balanceOfB(), investedA, investedB);
        if (ratioA >= ratioB) {
            return (tokenB, 0);
        }
        return (tokenA, 0);
    }

    function getPair() internal view override returns (address) {
        address factory = ISolidRouter(router).factory();
        return ISolidFactory(factory).getPair(tokenA, tokenB, stable);
    }

    function estimatedTotalAssetsAfterBalance()
        public
        view
        override
        returns (uint256 _aBalance, uint256 _bBalance)
    {
        uint256 rewardsPending = pendingReward().add(balanceOfReward());

        (_aBalance, _bBalance) = balanceOfTokensInLP();

        _aBalance = _aBalance.add(balanceOfA());
        _bBalance = _bBalance.add(balanceOfB());

        (uint256 callProfit, uint256 putProfit) = getHedgeProfit();
        _aBalance = _aBalance.add(callProfit);
        _bBalance = _bBalance.add(putProfit);

        if (reward == tokenA) {
            _aBalance = _aBalance.add(rewardsPending);
        } else if (reward == tokenB) {
            _bBalance = _bBalance.add(rewardsPending);
        } else if (rewardsPending != 0) {
            address swapTo = findSwapTo(reward);
            uint256[] memory outAmounts =
                ISolidRouter(router).getAmountsOut(
                    rewardsPending,
                    getTokenOutPathSolid(reward, swapTo)
                );
            if (swapTo == tokenA) {
                _aBalance = _aBalance.add(outAmounts[outAmounts.length - 1]);
            } else if (swapTo == tokenB) {
                _bBalance = _bBalance.add(outAmounts[outAmounts.length - 1]);
            }
        }

        (address sellToken, uint256 sellAmount) =
            calculateSellToBalance(_aBalance, _bBalance, investedA, investedB);

        (uint256 reserveA, uint256 reserveB) = getReserves();

        if (sellToken == tokenA) {
            uint256 buyAmount =
                ISolidlyPair(address(pair)).getAmountOut(sellAmount, sellToken);
            _aBalance = _aBalance.sub(sellAmount);
            _bBalance = _bBalance.add(buyAmount);
        } else if (sellToken == tokenB) {
            uint256 buyAmount =
                ISolidlyPair(address(pair)).getAmountOut(sellAmount, sellToken);
            _bBalance = _bBalance.sub(sellAmount);
            _aBalance = _aBalance.add(buyAmount);
        }
    }

    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view override returns (address _sellToken, uint256 _sellAmount) {
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        (uint256 ratioA, uint256 ratioB) =
            getRatios(currentA, currentB, startingA, startingB);

        if (ratioA == ratioB) return (address(0), 0);

        (uint256 reserveA, uint256 reserveB) = getReserves();

        if (ratioA > ratioB) {
            _sellToken = tokenA;
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentA,
                currentB,
                startingA,
                startingB,
                10**uint256(IERC20Extended(tokenA).decimals())
            );
        } else {
            _sellToken = tokenB;
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentB,
                currentA,
                startingB,
                startingA,
                10**uint256(IERC20Extended(tokenB).decimals())
            );
        }
    }

    function _calculateSellToBalance(
        address sellToken,
        uint256 current0,
        uint256 current1,
        uint256 starting0,
        uint256 starting1,
        uint256 precision
    ) internal view returns (uint256 _sellAmount) {
        uint256 numerator =
            current0.sub(starting0.mul(current1).div(starting1)).mul(precision);
        uint256 exchangeRate =
            ISolidlyPair(address(pair)).getAmountOut(precision, sellToken);

        // First time to approximate
        _sellAmount = numerator.div(
            precision + starting0.mul(exchangeRate).div(starting1)
        );
        // Shortcut to avoid Uniswap amountIn == 0 revert
        if (_sellAmount == 0) {
            return 0;
        }

        // Second time to account for price impact
        exchangeRate = ISolidlyPair(address(pair))
            .getAmountOut(_sellAmount, sellToken)
            .mul(precision)
            .div(_sellAmount);
        _sellAmount = numerator.div(
            precision + starting0.mul(exchangeRate).div(starting1)
        );
    }

    function getYSwapTokens()
        internal
        view
        override
        returns (address[] memory, address[] memory)
    {
        address[] memory tokens = new address[](2);
        address[] memory toTokens = new address[](2);

        tokens[0] = SEX;
        toTokens[0] = address(tokenA); // swap to tokenA

        tokens[1] = SOLID_SEX;
        toTokens[1] = address(tokenA); // swap to tokenA

        return (tokens, toTokens);
    }

    function removeTradeFactoryPermissions()
        external
        override
        onlyVaultManagers
    {
        _removeTradeFactory();
    }

    function updateTradeFactoryPermissions(address _newTradeFactory)
        external
        override
        onlyGovernance
    {
        _updateTradeFactory(_newTradeFactory);
    }
}
