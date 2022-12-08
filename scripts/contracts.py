from brownie import GammaFarm, GammaFarmTestOnly, UniswapV3Staker
from brownie import TestPriceFeed
from brownie import accounts, network
import getpass
import json
import os

NFT_POSITIONS_MANAGER_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
UNISWAP_V3_FACTORY_ADDRESS = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

ABIS_DIRECTORY = "www/src/artifacts/deployments"


def deploy_gamma_farm_test_only(mal_to_distribute, mal_distribution_period_secs, mal_reward_per_sec, mal_decay_factor, mal_decay_period_secs, owner):
    return deploy(GammaFarmTestOnly, args=[mal_to_distribute, mal_distribution_period_secs, mal_reward_per_sec, mal_decay_factor, mal_decay_period_secs], creator=owner)


def deploy_gamma_farm(mal_to_distribute, mal_distribution_period_secs, mal_reward_per_sec, mal_decay_factor, mal_decay_period_secs, owner):
    return deploy(GammaFarm, args=[mal_to_distribute, mal_distribution_period_secs, mal_reward_per_sec, mal_decay_factor, mal_decay_period_secs], creator=owner)


def deploy_v3_staker(creator=None):
    return deploy(
        UniswapV3Staker,
        args=[
            UNISWAP_V3_FACTORY_ADDRESS,
            NFT_POSITIONS_MANAGER_ADDRESS,
            2 ** 32,  # maxIncentiveStartLeadTime
            2 ** 32,  # maxIncentiveDuration
        ],
        creator=creator,
    )


def deploy_test_price_feed(price, creator=None):
    creator = creator or accounts[1]
    return TestPriceFeed.deploy(price, {'from': creator})


def deploy(obj, args=[], creator=None):
    if network.show_active() == 'mainnet':
        assert creator is not None
        print(f"You are about to deploy {obj._name} contract onto Ethereum Mainnet")
        pk = getpass.getpass(f"Enter creator address ({creator}) private key: ")
        creator_acc = accounts.add(f"{'0x' if not pk.startswith('0x') else ''}{pk}")
        if creator_acc.address.lower() != creator.lower():
            raise Exception("Invalid private key")
        creator = creator_acc
    # Resolve default parameters:
    creator = creator or accounts[1]
    # Deploy:
    assert(os.path.isdir(ABIS_DIRECTORY))
    print(f'Deploying {obj._name}...')
    contract = obj.deploy(*args, {'from': creator})
    network_key = network.show_active()
    # Update ABI
    abi_dir = f"{ABIS_DIRECTORY}/{network_key}"
    if not os.path.isdir(abi_dir):
        os.makedirs(abi_dir)
    abi_file = f"{abi_dir}/{contract.address}.json"
    with open(abi_file, "w") as f:
        f.write(json.dumps(contract.abi))
    print(f"Saved ABI to '{abi_file}'")
    # Update map.json
    map_file = f"{ABIS_DIRECTORY}/map.json"
    map_obj = {}
    if os.path.exists(map_file):
        with open(map_file, "r") as f:
            map_obj = json.loads(f.read())
    if network_key not in map_obj:
        map_obj[network_key] = {}
    if contract._name in map_obj[network_key]:
        prev_address = map_obj[network_key][contract._name]
        if prev_address != contract.address and os.path.exists(f"{abi_dir}/{prev_address}.json"):
            os.remove(f"{abi_dir}/{prev_address}.json")
    map_obj[network_key][contract._name] = contract.address
    with open(map_file, "w") as f:
        f.write(json.dumps(map_obj))
    return contract