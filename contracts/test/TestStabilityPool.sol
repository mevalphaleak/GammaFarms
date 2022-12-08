// SPDX-License-Identifier: GPL-3.0
pragma solidity =0.7.6;

import '../interfaces/lusd/IStabilityPool.sol';
import '../interfaces/lusd/ILUSDToken.sol';

contract TestStabilityPool is IStabilityPool {
    uint256 public totalLUSDDeposits;
    ILUSDToken constant public lusdToken = ILUSDToken(0x5f98805A4E8be255a32880FDeC7F6728C6568bA0);

    function provideToSP(uint _amount, address _frontEndTag) external override {
        lusdToken.transferFrom(msg.sender, address(this), _amount);
        totalLUSDDeposits += _amount;
    }

    function withdrawFromSP(uint _amount) external override {
        _amount = _amount < totalLUSDDeposits ? _amount : totalLUSDDeposits;
        if (_amount > 0) {
            lusdToken.transfer(msg.sender, _amount);
        }
        totalLUSDDeposits -= _amount;
    }

    function getCompoundedLUSDDeposit(address _depositor) external override view returns (uint) {
        return totalLUSDDeposits;
    }

    function setCompoundedLUSDDeposit(uint256 _totalLUSDDeposits) public {
        require(_totalLUSDDeposits <= totalLUSDDeposits);
        uint256 lossLUSD = totalLUSDDeposits - _totalLUSDDeposits;
        if (lossLUSD > 0) {
            lusdToken.transfer(address(0x000000000000000000000000000000000000dEaD), lossLUSD);
        }
        totalLUSDDeposits = _totalLUSDDeposits;
    }

    function withdrawETHGainToTrove(address _upperHint, address _lowerHint) external override {}
    function registerFrontEnd(uint _kickbackRate) external override {}
    function offset(uint _debt, uint _coll) external override {}
    function getETH() external override view returns (uint) {return 0;}
    function getTotalLUSDDeposits() external override view returns (uint) {return 0;}
    function getDepositorETHGain(address _depositor) external override view returns (uint) {return 0;}
    function getDepositorLQTYGain(address _depositor) external override view returns (uint) {return 0;}
    function getFrontEndLQTYGain(address _frontEnd) external override view returns (uint) {return 0;}
    function getCompoundedFrontEndStake(address _frontEnd) external override view returns (uint) {return 0;}
    function setAddresses(
        address _borrowerOperationsAddress,
        address _troveManagerAddress,
        address _activePoolAddress,
        address _lusdTokenAddress,
        address _sortedTrovesAddress,
        address _priceFeedAddress,
        address _communityIssuanceAddress
    ) external override {}
    receive() external payable {}
}
