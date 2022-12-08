// SPDX-License-Identifier: GPL-3.0
pragma solidity =0.7.6;

import '../interfaces/oracle/IPriceFeed.sol';

contract TestPriceFeed is IPriceFeed {
    uint public lastGoodPrice;

    constructor(uint256 _lastGoodPrice) public {
        lastGoodPrice = _lastGoodPrice;
    }

    function fetchPrice() external override returns (uint) {
        return lastGoodPrice;
    }

    function setPrice(uint price) public {
        emit LastGoodPriceUpdated(price);
        lastGoodPrice = price;
    }
}
