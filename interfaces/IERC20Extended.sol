pragma solidity 0.6.12;
import {IERC20} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

interface IERC20Extended is IERC20 {
    function decimals() external view returns (uint8);

    function name() external view returns (string memory);

    function symbol() external view returns (string memory);
}
