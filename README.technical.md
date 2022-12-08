## Project structure

bots/ - Code for bots tracking emergency and starting new epochs

contracts/ - Solidity code for smart-contracts

scripts/ - various scripts to help with contracts deployment, testing, ...

tests/ - tests for contracts

www/ - React-application


## Installation
For contracts development and testing we use [Brownie](https://eth-brownie.readthedocs.io/en/stable/). Installation instructions [here](https://github.com/eth-brownie/brownie#installation). (Tested with v1.18.1)

Under the hood it uses [Ganache](https://github.com/trufflesuite/ganache) for running forked version of mainnet blockchain. (Tested with v7.0.1)

## Contracts Development
Once you write a contract, you can interact with it via Brownie console with environment configured in ```brownie-config.yaml``` (by default it will launch forked mainnet locally). This file also specifies accounts to be unlocked and funded with test Ethereum.

```
brownie console
> run('tokens', 'fund_lusd')  # running 'fund_lusd' method from scripts/tokens.py to fund account with LUSD
> farm = accounts[0].deploy(GammaFarm)
> farm.deposit(int(1e18), {'from': accounts[0]})  # contract call (optionally you can specify 'from' and other tx fields)
> farm.withdraw({'from': accounts[0]})
```

You can also call methods from scripts using ```brownie run``` e.g. the following command will run ```mainnet_fork``` method from ```scripts/setup.py``` file:
```
brownie run setup mainnet_fork
```

You can also write some tests and run them using:
```
brownie test tests/instamine/test_farm_gas.py
```

## Run website
All web stuff resides in ```www/``` folder. First, install all dependencies (done once):
```
cd www
yarn install
```

You can start website by running:
```
yarn start
```

### Connect Metamask with mainnet-fork:
1) Run ```setup-mainnet-fork.sh``` from project root folder. This will launch mainnet fork, deploy all contracts and fund accounts. Fork will be launched on port=9545.
```
bash setup-mainnet-fork.sh
```
2) Locally on your computer run (assuming you develop remotely):
```
ssh -L 3000:localhost:3000 -i ~/.ssh/id_file user@host
ssh -L 9545:localhost:9545 -i ~/.ssh/id_file user@host
```
3) Add custom network to Metamask (ChainID: 1, Endpoint: http://localhost:9545) (done once)
4) Add funded accounts to Metamask (using private keys or mnemonic in ```brownie-config.yaml```) (done once)
5) Run website:
```
yarn start
```
6) Website will be accessible on: http://localhost:3000


## Issues
- Because Metamask keeps track of transactions locally, if mainnet-fork will be restarted then it will likely mess up transaction nonces. As a workaround either: do "Advanced > Reset Account" in Metamask after every mainnet-fork restart (this will clean history) or specify nonce manually in Metamask every time tx is signed.
- Forked mainnet without an archive node has a limited lifespan - if you encounter error like "Project ID does not have access to archive state", it's time to restart your blockchain.
