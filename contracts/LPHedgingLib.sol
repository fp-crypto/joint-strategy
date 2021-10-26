pragma solidity 0.6.12;

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "@openzeppelin/contracts/math/Math.sol";
import "../interfaces/uni/IUniswapV2Pair.sol";
import "../interfaces/hegic/IHegicOptions.sol";
import "../interfaces/IERC20Extended.sol";

interface IPriceProvider {
    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );
}

interface HegicJointAPI {
    function hegicCallOptionsPool() external view returns (address);

    function hegicPutOptionsPool() external view returns (address);
}

library LPHedgingLib {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;
    using Address for address;

    address public constant hegicOptionsManager =
        0x1BA4b447d0dF64DA64024e5Ec47dA94458C1e97f;

    uint256 private constant MAX_BPS = 10_000;

    function _checkAllowance(
        uint256 callAmount,
        uint256 putAmount,
        uint256 period
    ) internal {
        IERC20 _token;
        IHegicPool hegicCallOptionsPool = _hegicCallOptionsPool();
        IHegicPool hegicPutOptionsPool = _hegicPutOptionsPool();
        _token = hegicCallOptionsPool.token();
        if (
            _token.allowance(address(hegicCallOptionsPool), address(this)) <
            getOptionCost(hegicCallOptionsPool, period, callAmount)
        ) {
            _token.approve(address(hegicCallOptionsPool), type(uint256).max);
        }

        _token = hegicPutOptionsPool.token();
        if (
            _token.allowance(address(hegicPutOptionsPool), address(this)) <
            getOptionCost(hegicPutOptionsPool, period, putAmount)
        ) {
            _token.approve(address(hegicPutOptionsPool), type(uint256).max);
        }
    }

    function getCurrentPrice() public returns (uint256) {
        IPriceProvider pp =
            IPriceProvider(_hegicCallOptionsPool().priceProvider());
        (, int256 answer, , , ) = pp.latestRoundData();
        return uint256(answer);
    }

    function _hegicCallOptionsPool() internal view returns (IHegicPool) {
        return IHegicPool(HegicJointAPI(address(this)).hegicCallOptionsPool());
    }

    function _hegicPutOptionsPool() internal view returns (IHegicPool) {
        return IHegicPool(HegicJointAPI(address(this)).hegicPutOptionsPool());
    }

    function hedgeLPToken(
        address lpToken,
        uint256 h,
        uint256 period
    )
        external
        returns (
            uint256 callID,
            uint256 putID,
            uint256 strike
        )
    {
        IHegicPool hegicCallOptionsPool = _hegicCallOptionsPool();
        IHegicPool hegicPutOptionsPool = _hegicPutOptionsPool();
        uint256 q = getLPInfo(lpToken, hegicCallOptionsPool);
        if (h == 0 || period == 0 || q == 0) {
            return (0, 0, 0);
        }

        (uint256 putAmount, uint256 callAmount) = getOptionsAmount(q, h);

        _checkAllowance(callAmount, putAmount, period);
        callID = buyOptionFrom(hegicCallOptionsPool, callAmount, period);
        putID = buyOptionFrom(hegicPutOptionsPool, putAmount, period);
        strike = getCurrentPrice();
    }

    function getOptionCost(
        IHegicPool pool,
        uint256 period,
        uint256 amount
    ) public view returns (uint256) {
        // Strike = 0 means ATM option
        (uint256 premium, uint256 settlementFee) =
            pool.calculateTotalPremium(period, amount, 0);
        return premium + settlementFee;
    }

    function getOptionsProfit(uint256 callID, uint256 putID)
        external
        view
        returns (uint256, uint256)
    {
        return (getCallProfit(callID), getPutProfit(putID));
    }

    function getCallProfit(uint256 id) internal view returns (uint256) {
        if (id == 0) {
            return 0;
        }
        return _hegicCallOptionsPool().profitOf(id);
    }

    function getPutProfit(uint256 id) internal view returns (uint256) {
        if (id == 0) {
            return 0;
        }
        return _hegicPutOptionsPool().profitOf(id);
    }

    function closeHedge(uint256 callID, uint256 putID)
        external
        returns (
            uint256 payoutToken0,
            uint256 payoutToken1,
            uint256 exercisePrice
        )
    {
        IHegicPool hegicCallOptionsPool = _hegicCallOptionsPool();
        IHegicPool hegicPutOptionsPool = _hegicPutOptionsPool();
        uint256 callProfit = hegicCallOptionsPool.profitOf(callID);
        uint256 putProfit = hegicPutOptionsPool.profitOf(putID);

        // Check the options have not expired
        // NOTE: call and put options expiration MUST be the same
        (, , , , uint256 expired, , ) = hegicCallOptionsPool.options(callID);
        if (expired < block.timestamp) {
            return (0, 0, 0);
        }

        if (callProfit > 0) {
            // call option is ITM
            hegicCallOptionsPool.exercise(callID);
        }

        if (putProfit > 0) {
            // put option is ITM
            hegicPutOptionsPool.exercise(putID);
        }
        exercisePrice = getCurrentPrice();
    }

    function getOptionsAmount(uint256 q, uint256 h)
        public
        view
        returns (uint256 putAmount, uint256 callAmount)
    {
        callAmount = getCallAmount(q, h);
        putAmount = getPutAmount(q, h);
    }

    function getCallAmount(uint256 q, uint256 h) public view returns (uint256) {
        uint256 one = MAX_BPS;
        return
            one
                .sub(uint256(2).mul(one).mul(sqrt(one.add(h)).sub(one)).div(h))
                .mul(q)
                .div(MAX_BPS); // 1 - 2 / h * (sqrt(1 + h) - 1)
    }

    function getPutAmount(uint256 q, uint256 h) public view returns (uint256) {
        uint256 one = MAX_BPS;
        return
            uint256(2)
                .mul(one)
                .mul(one.sub(sqrt(one.sub(h))))
                .div(h)
                .sub(one)
                .mul(q)
                .div(MAX_BPS); // 2 * (1 - sqrt(1 - h)) / h - 1
    }

    function buyOptionFrom(
        IHegicPool pool,
        uint256 amount,
        uint256 period
    ) internal returns (uint256) {
        return pool.sellOption(address(this), period, amount, 0); // strike = 0 is ATM
    }

    function getLPInfo(address lpToken, IHegicPool hegicCallOptionsPool)
        public
        view
        returns (uint256 q)
    {
        uint256 amount = IUniswapV2Pair(lpToken).balanceOf(address(this));

        address token0 = IUniswapV2Pair(lpToken).token0();
        address token1 = IUniswapV2Pair(lpToken).token1();

        uint256 balance0 = IERC20(token0).balanceOf(address(lpToken));
        uint256 balance1 = IERC20(token1).balanceOf(address(lpToken));
        uint256 totalSupply = IUniswapV2Pair(lpToken).totalSupply();

        uint256 token0Amount = amount.mul(balance0) / totalSupply;
        uint256 token1Amount = amount.mul(balance1) / totalSupply;

        address mainAsset = address(hegicCallOptionsPool.token());
        if (mainAsset == token0) {
            q = token0Amount;
        } else if (mainAsset == token1) {
            q = token1Amount;
        } else {
            revert("LPtoken not supported");
        }
    }

    function getTimeToMaturity(uint256 callID, uint256 putID)
        public
        view
        returns (uint256)
    {
        if (callID == 0 || putID == 0) {
            return 0;
        }
        (, , , , uint256 expiredCall, , ) =
            _hegicCallOptionsPool().options(callID);
        (, , , , uint256 expiredPut, , ) =
            _hegicPutOptionsPool().options(putID);
        // use lowest time to maturity (should be the same)
        uint256 expired = expiredCall > expiredPut ? expiredPut : expiredCall;
        if (expired < block.timestamp) {
            return 0;
        }
        return expired.sub(block.timestamp);
    }

    function getHedgeStrike(uint256 callID, uint256 putID)
        public
        view
        returns (uint256)
    {
        // NOTE: strike is the same for both options
        (, uint256 strikeCall, , , , , ) =
            _hegicCallOptionsPool().options(callID);
        return strikeCall;
    }

    function sqrt(uint256 x) public pure returns (uint256 result) {
        x = x.mul(MAX_BPS);
        result = x;
        uint256 k = (x >> 1) + 1;
        while (k < result) (result, k) = (k, (x / k + k) >> 1);
    }
}
