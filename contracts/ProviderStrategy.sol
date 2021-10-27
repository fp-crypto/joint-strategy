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
import "@openzeppelin/contracts/math/Math.sol";
import {BaseStrategy} from "@yearnvaults/contracts/BaseStrategy.sol";

interface IERC20Extended {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}

interface JointAPI {
    function prepareReturn(bool returnFunds) external;

    function adjustPosition() external;

    function providerA() external view returns (address);

    function providerB() external view returns (address);

    function estimatedTotalAssetsInToken(address token)
        external
        view
        returns (uint256);

    function WETH() external view returns (address);

    function router() external view returns (address);
}

contract ProviderStrategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    address public joint;
    bool public takeProfit;
    bool public investWant;

    constructor(address _vault) public BaseStrategy(_vault) {
        _initializeStrat();
    }

    function initialize(
        address _vault,
        address _strategist,
        address _rewards,
        address _keeper
    ) external {
        _initialize(_vault, _strategist, _rewards, _keeper);
        _initializeStrat();
    }

    function _initializeStrat() internal {
        investWant = true;
        takeProfit = false;
    }

    event Cloned(address indexed clone);

    function cloneProviderStrategy(
        address _vault,
        address _strategist,
        address _rewards,
        address _keeper
    ) external returns (address newStrategy) {
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
            newStrategy := create(0, clone_code, 0x37)
        }

        ProviderStrategy(newStrategy).initialize(
            _vault,
            _strategist,
            _rewards,
            _keeper
        );

        emit Cloned(newStrategy);
    }

    function name() external view override returns (string memory) {
        return
            string(
                abi.encodePacked(
                    "ProviderOf",
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

    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        JointAPI(joint).prepareReturn(!investWant || takeProfit);

        // if we are not taking profit, there is nothing to do
        if (!takeProfit) {
            return (0, 0, 0);
        }

        uint256 totalDebt = vault.strategies(address(this)).totalDebt;
        uint256 totalAssets = balanceOfWant();

        if (totalDebt > totalAssets) {
            // we have losses
            _loss = totalDebt.sub(totalAssets);
        } else {
            // we have profit
            _profit = totalAssets.sub(totalDebt);
        }

        // free funds to repay debt + profit to the strategy
        uint256 amountAvailable = totalAssets;
        uint256 amountRequired = _debtOutstanding.add(_profit);

        if (amountRequired > amountAvailable) {
            if (amountAvailable < _debtOutstanding) {
                // available funds are lower than the repayment that we need to do
                _profit = 0;
                _debtPayment = amountAvailable;
                // we dont report losses here as the strategy might not be able to return in this harvest
                // but it will still be there for the next harvest
            } else {
                // NOTE: amountRequired is always equal or greater than _debtOutstanding
                // important to use amountRequired just in case amountAvailable is > amountAvailable
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

    function adjustPosition(uint256 _debtOutstanding) internal override {
        if (emergencyExit) {
            return;
        }

        // If we shouldn't invest, don't do it :D
        if (!investWant) {
            return;
        }

        uint256 wantBalance = balanceOfWant();
        if (wantBalance > 0) {
            want.transfer(joint, wantBalance);
        }
        JointAPI(joint).adjustPosition();
    }

    function liquidatePosition(uint256 _amountNeeded)
        internal
        override
        returns (uint256 _liquidatedAmount, uint256 _loss)
    {
        uint256 totalAssets = want.balanceOf(address(this));
        if (_amountNeeded > totalAssets) {
            _liquidatedAmount = totalAssets;
            _loss = _amountNeeded.sub(totalAssets);
        } else {
            _liquidatedAmount = _amountNeeded;
        }
    }

    function prepareMigration(address _newStrategy) internal override {
        // Want is sent to the new strategy in the base class
        // nothing to do here
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
        );
        joint = _joint;
    }

    function setTakeProfit(bool _takeProfit) external onlyAuthorized {
        takeProfit = _takeProfit;
    }

    function setInvestWant(bool _investWant) external onlyAuthorized {
        investWant = _investWant;
    }

    function liquidateAllPositions()
        internal
        virtual
        override
        returns (uint256 _amountFreed)
    {
        JointAPI(joint).prepareReturn(true);
        _amountFreed = balanceOfWant();
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
}
