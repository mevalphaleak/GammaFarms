MAINNET_ENDPOINT = "https://rpc.flashbots.net"
MAINNET_FORK_ENDPOINT = "http://localhost:9545"

GAMMA_FARM_DEV_ADDRESS = "0xF7b4E35F5Fb826d1AdDdA69ad25c5D885fA2DD15"

CONFIG = {
    "mainnet": {
        "WEB3_ENDPOINT": MAINNET_ENDPOINT,
        "WEB3_PRIVATE_ENDPOINT": MAINNET_ENDPOINT,
        "GAMMA_FARM_ADDRESS": "0x5Dc58f812b2e244DABA2fabd33f399cD699D7Ddc",
        "GAMMA_FARM_ABI_PATH": "abi/GammaFarm.json",
        "LOG_PATH": "~/logs/gamma_farm_bot.log",
    },
    "mainnet-fork": {
        "WEB3_ENDPOINT": MAINNET_FORK_ENDPOINT,
        "GAMMA_FARM_ADDRESS": GAMMA_FARM_DEV_ADDRESS,
        "GAMMA_FARM_ABI_PATH": f"../www/src/artifacts/deployments/mainnet-fork/{GAMMA_FARM_DEV_ADDRESS}.json",
        "LOG_PATH": "gamma_farm_bot.dev.log",
    }
}
