// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

interface IHedgilV1 {
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
