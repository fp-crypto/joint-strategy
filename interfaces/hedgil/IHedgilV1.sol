// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IHedgilPool is IERC20 {
    event Provide(address indexed account, uint256 amount, uint256 shares);

    event Withdraw(address indexed account, uint256 amount, uint256 shares);

    function provideLiquidity(
        uint256 amount,
        uint256 minMint,
        address onBehalfOf
    ) external returns (uint256 shares);

    function shareOf(address account) external view returns (uint256);

    function withdrawAllLiquidity() external returns (uint256 amount);

    function withdrawUnderlying(uint256 amount, uint256 maxBurn)
        external
        returns (uint256 shares);

    function withdrawShares(uint256 shares, uint256 minAmount)
        external
        returns (uint256 amount);
}

interface IHedgilV1 is IHedgilPool {
    event OpenHedgil(
        address indexed owner,
        uint256 indexed id,
        uint256 expiration,
        uint256 strike,
        uint256 initialQ,
        uint256 cost
    );

    event CloseHedgil(
        address indexed owner,
        uint256 indexed id,
        uint256 cost,
        uint256 payout
    );

    struct Hedgil {
        address owner;
        uint256 id;
        uint256 initialQ;
        uint256 strike;
        uint256 maxPriceChange;
        uint256 expiration;
        uint256 cost;
    }

    function hedgils(uint256 id) external view returns (Hedgil memory hedgil);

    function quoteToken() external view returns (IERC20);

    function openHedgil(
        uint256 lpAmount,
        uint256 maxPriceChange,
        uint256 period,
        address onBehalfOf
    ) external returns (uint256 hedgilID);

    function closeHedgil(uint256 _hedgilID) external returns (uint256 payout);

    function getCurrentPayout(uint256 _hedgilID)
        external
        view
        returns (uint256);

    function getHedgilQuote(
        uint256 q,
        uint256 h,
        uint256 period
    ) external view returns (uint256 quote);
}
