[Technical project readme](README.technical.md)

Deployment: [https://gammafarms.eth.limo](https://gammafarms.eth.limo)

IPFS: `ipfs://bafybeiabzhnbuo4q2qynkyb2s2dxpfegezvvhewkwnfatib2gyfim5cfpa/#/`

[Code on Etherscan](https://etherscan.io/address/0x5Dc58f812b2e244DABA2fabd33f399cD699D7Ddc#code)

For a long time I was personally yield farming `LUSD` inside stability pool since I consider it the only reliable decentralised stable-coin which can't be easily corrupted by gorvernance. Though providing `LUSD` to stability pool also has 2 pit falls:
1) You can [loose money](https://docs.liquity.org/faq/stability-pool-and-liquidations#can-i-lose-money-by-depositing-funds-to-the-stability-pool) if `LUSD` trades above 1.1$(or even slightly lower) during liquidations.
2) You have to often rebase your position disposing of `ETH`(from liquidations) and `LQTY`(from yield farming).

To address (1) there's a script [implemented](bots/gamma_farm_bot.py#L197) which pulls `LUSD` from stability pool if next oracle update can cause a loss of funds via liquidations.
To address (2) and keep rebase costs low relative to farm's size I've decided to make this gamma farm public.

To bootsrap the farm the plan is to use same worthless shit-coin that was distributed among early users of my previous projects: [MAL token](https://fractional.art/vaults/0x6619078bdd8324e01e9a8d4b3d761b050e5ecf06)

Early users of BetaRPC endpoint and winners of AlphaMEV contest also received same useless token repsenting fractional ownership of few pixels.
