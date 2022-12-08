// SPDX-License-Identifier: GPL-2.0-or-later
pragma solidity >=0.7.6;
pragma abicoder v2;

import '@uniswap/v3-staker/contracts/interfaces/IUniswapV3Staker.sol';
import '@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol';

contract MalTokenStakerHelper {
    address public constant MAL_token  = address(0x6619078Bdd8324E01E9a8D4b3d761b050E5ECF06);
    address public constant WETH_token = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    address public constant UNI_staker = address(0x1f98407aaB862CdDeF78Ed252D6f557aA5b0f00d);
    INonfungiblePositionManager public constant manager = INonfungiblePositionManager(0xC36442b4a4522E871399CD717aBDD847Ab11FE88);

    function checkTokenValidLiquidity(uint256 tokenId) public view returns(uint128 result) {
        (
            ,
            ,
            address token0,
            address token1,
            uint24 fee,
            ,
            ,
            uint128 liquidity,
            ,
            ,
            ,
        ) = manager.positions(tokenId);
        if (token0 != MAL_token) return 0;
        if (token1 != WETH_token) return 0;
        if (fee != 3000) return 0;
        return liquidity;
    }

    function findOwnerTokensInRange(address owner, uint256 minPosition, uint256 maxPosition) public view returns (uint256[] memory tokenIdsInRange) {
        uint256 ownerTokens = manager.balanceOf(owner);
        maxPosition = (maxPosition == 0 || ownerTokens < maxPosition) ? ownerTokens : maxPosition;
        uint256[] memory buf = new uint256[](maxPosition - minPosition);
        uint256 tokensFound = 0;
        for(uint256 index = minPosition; index < maxPosition; ++index) {
            uint256 tokenId = manager.tokenOfOwnerByIndex(owner, index);
            if (checkTokenValidLiquidity(tokenId) > 0) {
                buf[index - minPosition] = tokenId;
                tokensFound += 1;
            }
        }
        tokenIdsInRange = new uint256[](tokensFound);
        uint256 tokenPosition = 0;
        for(uint256 index = minPosition; index < maxPosition; ++index) {
            if (buf[index - minPosition] > 0) {
                tokenIdsInRange[tokenPosition] = buf[index - minPosition];
                tokenPosition += 1;
            }
        }
        return tokenIdsInRange;
    }

    function findAllValidPositions(address owner) public view
        returns (
            uint256[] memory validTokenIds,
            address[] memory validTokenOwner,
            uint256[] memory validTokenLiquidity,
            uint48[] memory validTokenStakes
        )
    {
        uint256[] memory ownerTokens  = findOwnerTokensInRange(owner, 0, 0);
        uint256[] memory stakerTokens = findOwnerTokensInRange(UNI_staker, 0, 0);
        uint256 ownerTotalTokens = ownerTokens.length;
        for (uint256 id = 0; id < stakerTokens.length; ++id) {
            (
                address tokenOwner,
                ,
                ,
            ) = IUniswapV3Staker(UNI_staker).deposits(stakerTokens[id]);
            if (tokenOwner != owner) {
                stakerTokens[id]  = 0;
            } else {
                ownerTotalTokens += 1;
            }
        }
        validTokenIds       = new uint256[] (ownerTotalTokens);
        validTokenOwner     = new address[] (ownerTotalTokens);
        validTokenLiquidity = new uint256[] (ownerTotalTokens);
        validTokenStakes    = new  uint48[] (ownerTotalTokens);
        for (uint256 id = 0; id < ownerTokens.length; ++id) {
            validTokenIds[id] = ownerTokens[id];
            validTokenOwner[id] = owner;
            validTokenLiquidity[id] = checkTokenValidLiquidity(ownerTokens[id]);
            validTokenStakes[id] = 0;
        }
        uint256 tokenPositionToUse = ownerTokens.length;
        for (uint256 id = 0; id < stakerTokens.length; ++id) {
            if (stakerTokens[id] == 0) continue;
            validTokenIds[tokenPositionToUse] = stakerTokens[id];
            validTokenOwner[tokenPositionToUse] = UNI_staker;
            validTokenLiquidity[tokenPositionToUse] = checkTokenValidLiquidity(stakerTokens[id]);
            (
                ,
                uint48 tokenStakes,
                ,
            ) = IUniswapV3Staker(UNI_staker).deposits(stakerTokens[id]);
            validTokenStakes[tokenPositionToUse] = tokenStakes;
            tokenPositionToUse++;
        }
    }
}