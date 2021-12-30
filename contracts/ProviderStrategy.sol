// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import "../interfaces/uni/IUniswapV2Router02.sol";
import "../interfaces/IERC20Extended.sol";
import "@openzeppelin/contracts/math/Math.sol";
import {
    BaseStrategyInitializable
} from "@yearnvaults/contracts/BaseStrategy.sol";

import "../interfaces/ironbank/CErc20Interface.sol";
import "../interfaces/ironbank/ComptrollerInterface.sol";

interface IPriceOracle {
    function getUnderlyingPrice(CErc20Interface ibToken)
        external
        view
        returns (uint256);
}

interface JointAPI {
    function closePositionReturnFunds() external;

    function openPosition() external;

    function providerA() external view returns (address);

    function providerB() external view returns (address);

    function estimatedTotalAssetsInToken(address token)
        external
        view
        returns (uint256);

    function WETH() external view returns (address);

    function router() external view returns (address);

    function migrateProvider(address _newProvider) external view;

    function shouldEndEpoch() external view returns (bool);

    function dontInvestWant() external view returns (bool);
}

interface IPriceProvider {
    function latestAnswer() external view returns (uint);
}

contract LevProviderStrategy is BaseStrategyInitializable {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    CErc20Interface public ibToken;
    ComptrollerInterface public comptrollerIB;

    IPriceProvider public priceProvider = IPriceProvider(0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419);

    address public joint;

    bool public forceLiquidate;

    uint256 internal constant BLOCKS_PER_YEAR = 2_102_400;

    constructor(address _vault, CErc20Interface _ibToken, ComptrollerInterface _comptrollerIB) public BaseStrategyInitializable(_vault) {
        comptrollerIB = _comptrollerIB;
        ibToken = _ibToken;
        IERC20 _borrowedToken = IERC20(_ibToken.underlying());
        _borrowedToken.safeApprove(address(_ibToken), type(uint256).max);
    }

    function name() external view override returns (string memory) {
        return
            string(
                abi.encodePacked(
                    "Strategy_ProviderOf",
                    IERC20Extended(address(want)).symbol(),
                    "To",
                    IERC20Extended(address(joint)).name()
                )
            );
    }

    function estimatedTotalAssets() public view override returns (uint256) {
        return
            want.balanceOf(address(this)).add(
                JointAPI(joint).estimatedTotalAssetsInToken(address(want))
            );
    }

    function totalDebt() public view returns (uint256) {
        return vault.strategies(address(this)).totalDebt;
    }

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // NOTE: this strategy is operated following epochs. These begin during adjustPosition and end during prepareReturn
        // The Provider will always ask the joint to close the position before harvesting
        JointAPI(joint).closePositionReturnFunds();

        // Repay debt
        if(balanceOfDebt() > 0) {
            repayFullDebt();
        }

        // After closePosition, the provider will always have funds in its own balance (not in joint)
        uint256 _totalDebt = totalDebt();
        uint256 totalAssets = balanceOfWant();

        if (_totalDebt > totalAssets) {
            // we have losses
            _loss = _totalDebt.sub(totalAssets);
        } else {
            // we have profit
            _profit = totalAssets.sub(_totalDebt);
        }

        uint256 amountAvailable = totalAssets;
        uint256 amountRequired = _debtOutstanding.add(_profit);

        if (amountRequired > amountAvailable) {
            if (_debtOutstanding > amountAvailable) {
                // available funds are lower than the repayment that we need to do
                _profit = 0;
                _debtPayment = amountAvailable;
                // we dont report losses here as the strategy might not be able to return in this harvest
                // but it will still be there for the next harvest
            } else {
                // NOTE: amountRequired is always equal or greater than _debtOutstanding
                // important to use amountAvailable just in case amountRequired is > amountAvailable
                _debtPayment = _debtOutstanding;
                _profit = amountAvailable.sub(_debtPayment);
            }
        } else {
            _debtPayment = _debtOutstanding;
            // profit remains unchanged unless there is not enough to pay it
            if (amountRequired.sub(_debtPayment) < _profit) {
                _profit = amountRequired.sub(_debtPayment);
            }
        }
    }

    function harvestTrigger(uint256 callCost)
        public
        view
        override
        returns (bool)
    {
        // Delegating decision to joint
        return JointAPI(joint).shouldEndEpoch();
    }

    function dontInvestWant() public view returns (bool) {
        // Delegating decision to joint
        return JointAPI(joint).dontInvestWant();
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit || dontInvestWant()) {
            return;
        }

        // Take debt: this function will borrow an equivalent amount to the amount of want
        borrowRequiredAmountTokenB();
        uint256 bTokenBalance = balanceOfBorrowedToken();
        if(bTokenBalance > 0) {
            IERC20(borrowedToken()).transfer(joint, bTokenBalance);
        }

        // Using a push approach (instead of pull)
        uint256 wantBalance = balanceOfWant();
        if (wantBalance > 0) {
            want.transfer(joint, wantBalance);
        }
        JointAPI(joint).openPosition();

    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 availableAssets = want.balanceOf(address(this));
        if (_amountNeeded > availableAssets) {
            _liquidatedAmount = availableAssets;
            _loss = _amountNeeded.sub(availableAssets);
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function prepareMigration(address _newStrategy) internal override {
        // TODO: return debt! (handle levered balance before migrating)
        JointAPI(joint).migrateProvider(_newStrategy);
    }

    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    function balanceOfWant() public view returns (uint256) {
        return IERC20(want).balanceOf(address(this));
    }

    

    function setJoint(address _joint) external onlyGovernance {
        require(
            JointAPI(_joint).providerA() == address(this) ||
                JointAPI(_joint).providerB() == address(this)
        ); // dev: providers uncorrectly set
        require(healthCheck != address(0)); // dev: healthCheck
        joint = _joint;
    }

    function setForceLiquidate(bool _forceLiquidate)
        external
        onlyEmergencyAuthorized
    {
        forceLiquidate = _forceLiquidate;
    }

    function liquidateAllPositions()
        internal
        virtual
        override
        returns (uint256 _amountFreed)
    {
        uint256 expectedBalance = estimatedTotalAssets();
        JointAPI(joint).closePositionReturnFunds();
        
        _amountFreed = balanceOfWant();
        // NOTE: we accept a 1% difference before reverting
        require(
            forceLiquidate ||
                expectedBalance.mul(9_900).div(10_000) < _amountFreed,
            "!liquidation"
        );
    }

    function ethToWant(uint256 _amtInWei)
        public
        view
        override
        returns (uint256)
    {
        // NOTE: using joint params to avoid changing fixed values for other chains
        // gas price is not important as this will only be used in triggers (queried from off-chain)
        return tokenToWant(JointAPI(joint).WETH(), _amtInWei);
    }

    function tokenToWant(address token, uint256 amount)
        internal
        view
        returns (uint256)
    {
        if (amount == 0 || address(want) == token) {
            return amount;
        }

        uint256[] memory amounts =
            IUniswapV2Router02(JointAPI(joint).router()).getAmountsOut(
                amount,
                getTokenOutPath(token, address(want))
            );

        return amounts[amounts.length - 1];
    }

    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {
        bool is_weth =
            _token_in == address(JointAPI(joint).WETH()) ||
                _token_out == address(JointAPI(joint).WETH());
        _path = new address[](is_weth ? 2 : 3);
        _path[0] = _token_in;

        if (is_weth) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(JointAPI(joint).WETH());
            _path[2] = _token_out;
        }
    }

    function borrowedToken() public view returns(address) {
        return ibToken.underlying();
    }

    function balanceOfBorrowedToken() public view returns (uint) {
        return IERC20(borrowedToken()).balanceOf(address(this));
    }

    function updatedBalanceOfDebt() public returns (uint256) {
        return ibToken.borrowBalanceCurrent(address(this));
    }

    function balanceOfDebt() public view returns (uint256) {
        return ibToken.borrowBalanceStored(address(this));
    }

    function repayFullDebt() internal {
        repayBorrow(balanceOfDebt());
    }


    function borrowRequiredAmountTokenB() internal {
        // TODO: make this generic
    uint256 amountBToBorrow = balanceOfWant().mul(priceProvider.latestAnswer()).mul(uint(10)**IERC20Extended(borrowedToken()).decimals()).div(1e26);
        borrow(amountBToBorrow);
    }

    function borrow(uint256 amount) internal returns (uint256) {
        uint256 currentBorrow = updatedBalanceOfDebt();
        uint256 creditLimit =
            getCreditLimitInBorrowedToken(address(this));
        uint256 availableLimit = creditLimit > currentBorrow ? creditLimit - currentBorrow : 0;
        uint256 maxBorrow = Math.min(ibToken.getCash(), availableLimit);
        uint256 borrowAmount = Math.min(amount, maxBorrow);
        require(ibToken.borrow(borrowAmount) == 0);
        return borrowAmount;
    }

    function repayBorrow(uint256 amount) internal returns (uint256) {
        uint256 maxRepay = Math.min(balanceOfBorrowedToken(), balanceOfDebt());
        uint256 repayAmount = Math.min(amount, maxRepay);
        require(ibToken.repayBorrow(repayAmount) == 0);
        return repayAmount;
    }

    function currentBorrowingCosts() public view returns (uint256) {
        return ironBankBorrowRateAfterChange(0, false);
    }

    function ironBankBorrowRateAfterChange(uint256 amount, bool repay)
        public
        view
        returns (uint256 annualBorrowingCost)
    {
        uint256 borrowRatePerBlock =
            ibToken.estimateBorrowRatePerBlockAfterChange(amount, repay);

        // calculate estimated annual costs
        annualBorrowingCost = borrowRatePerBlock * BLOCKS_PER_YEAR;
    }

    function getCreditLimitInBorrowedToken(address account)
        public
        view
        returns (uint256)
    {
        // returns USD value in mantissa (1e18)
        uint256 usdCreditLimit = comptrollerIB.creditLimits(account);
        // if credit limit is infinite, we don't need to check anything else (otherwise, we will get an overflow)
        if (usdCreditLimit == type(uint256).max) {
            return type(uint256).max;
        }
        uint256 priceUSD = getBorrowedTokenPriceUSD();
        // we need to adjust price AND decimals
        // Using simplified version of:
        // uint256 wantCreditLimit = usdCreditLimit * 1e18 * (10 ** want.decimals()) / priceUSD / 1e18;
        uint256 wantCreditLimit =
            (usdCreditLimit * (uint256(10) ** IERC20Extended(borrowedToken()).decimals())) / priceUSD;
        return wantCreditLimit;
    }

    function getBorrowedTokenPriceUSD() public view returns (uint256) {
        return IPriceOracle(comptrollerIB.oracle()).getUnderlyingPrice(ibToken);
    }


}
