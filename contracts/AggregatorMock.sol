pragma solidity 0.6.12;

contract AggregatorMock {

    int256 public price;

    constructor(int256 _price) public {
        setPrice(_price);
    }

    function setPrice(int256 _price) public {
        price = _price;
    }

    function latestAnswer() external view returns (int256) {
        return price;
    }

    function latestRoundData() external view returns (
      uint80 roundId,
      int256 answer,
      uint256 startedAt,
      uint256 updatedAt,
      uint80 answeredInRound
    ) {
        return (uint80(0), price, uint256(0), uint256(0), uint80(0));
    }
}