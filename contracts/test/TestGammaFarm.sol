// SPDX-License-Identifier: GPL-3.0
pragma solidity =0.7.6;
pragma abicoder v2;

import '../GammaFarm.sol';
import '../interfaces/lusd/IStabilityPool.sol';

contract TestGammaFarm is GammaFarm {
    constructor(
        uint256 _malToDistribute,
        uint256 _malDistributionPeriodSeconds,
        uint256 _malRewardPerSecond,
        uint256 _malDecayFactor,
        uint256 _malDecayPeriodSeconds,
        address _lusdStabilityPoolAddress
    ) public GammaFarm(
        _malToDistribute,
        _malDistributionPeriodSeconds,
        _malRewardPerSecond,
        _malDecayFactor,
        _malDecayPeriodSeconds
    ) {
        lusdStabilityPool = IStabilityPool(_lusdStabilityPoolAddress);
        if (address(_lusdStabilityPoolAddress) != address(0x66017D22b0f8556afDd19FC67041899Eb65a21bb)) {
            lusdToken.approve(address(lusdStabilityPool), type(uint256).max);
        }
    }

    function _swapStabilityPoolRewardsForLUSD(bytes memory _data) internal override returns (uint256) {
        if (_data.length == 0) {
            return 0;
        }
        uint256 lusdReward = abi.decode(_data, (uint256));
        return lusdReward;
    }
}