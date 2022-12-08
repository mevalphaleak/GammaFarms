import argparse
import json
import os
import random
import signal
import sys
import time
import traceback

from datetime import timedelta
from eth_keyfile import extract_key_from_keyfile
from getpass import getpass
from web3 import Web3

from config import CONFIG
from epoch_trade_helper import EpochTradeHelper
from liquity_helper import LiquityHelper, MCR, CCR
from price_provider import PriceProvider

parser = argparse.ArgumentParser()
parser.add_argument("--mainnet", action='store_true', help="Use that to run on mainnet")
cmd_args = parser.parse_args()

NETWORK = "mainnet" if cmd_args.mainnet else "mainnet-fork"
GAMMA_FARM_ADDRESS = CONFIG[NETWORK]["GAMMA_FARM_ADDRESS"]
GAMMA_FARM_ABI = json.loads(open(CONFIG[NETWORK]["GAMMA_FARM_ABI_PATH"], "r").read())
WEB3_ENDPOINT = CONFIG[NETWORK]["WEB3_ENDPOINT"]
WEB3_PRIVATE_ENDPOINT = CONFIG[NETWORK]["WEB3_PRIVATE_ENDPOINT"]

LOG_PATH = os.path.expanduser(CONFIG[NETWORK]["LOG_PATH"])

w3 = Web3(Web3.HTTPProvider(WEB3_ENDPOINT, request_kwargs={'timeout':60}))
w3_private = Web3(Web3.HTTPProvider(WEB3_PRIVATE_ENDPOINT, request_kwargs={'timeout':60}))
w3_backup = Web3(Web3.HTTPProvider("https://rpc.builder0x69.io", request_kwargs={'timeout':60}))

LQTY_ADDRESS = "0x6DEA81C8171D0bA574754EF6F8b412F2Ed88c54D"
ERC20_ABI = json.loads(open(f"abi/ERC20.json", "r").read())

BASE_FEE_PER_GAS_LIMIT = w3.toWei('100', 'gwei')
PRIORITY_FEE_PER_GAS_LIMIT = w3.toWei('10', 'gwei')
GAS_BUMP_RATIO = 1.2

START_NEW_EPOCH_GAS_LIMIT = 1200000
EMERGENCY_WITHDRAW_GAS_LIMIT = 1200000
EMERGENCY_RECOVER_GAS_LIMIT = 1200000

LUSD_MIN_EMERGENCY_PRICE = 1.02

def log(*args):
    log_message = time.strftime('[%Y-%m-%d %H:%M:%S] ') + ' '.join(str(arg) for arg in args)
    with open(LOG_PATH, 'a') as log_file:
        log_file.write(log_message + '\n')
    print(log_message)


class GasStrategy:
    def __init__(self, initial_max_base_fee_per_gas_ratio, initial_max_priority_fee_per_gas=None):
        self.bump_ratio = GAS_BUMP_RATIO
        self.initial_max_base_fee_per_gas_ratio = initial_max_base_fee_per_gas_ratio
        self.initial_max_priority_fee_per_gas = initial_max_priority_fee_per_gas
        if self.initial_max_priority_fee_per_gas is None:
            self.initial_max_priority_fee_per_gas = w3.toWei('1', 'gwei')

    def fill_initial_gas_fees(self, tx):
        base_fee_per_gas = w3.eth.getBlock('pending').baseFeePerGas
        max_priority_fee_per_gas = self.initial_max_priority_fee_per_gas
        max_fee_per_gas = int(self.initial_max_base_fee_per_gas_ratio * base_fee_per_gas) + max_priority_fee_per_gas
        tx['maxPriorityFeePerGas'] = max_priority_fee_per_gas
        tx['maxFeePerGas'] = max_fee_per_gas

    def fill_next_gas_fees(self, tx):
        base_fee_per_gas = w3.eth.getBlock('pending').baseFeePerGas
        max_priority_fee_per_gas = int(tx['maxPriorityFeePerGas'] * self.bump_ratio)
        max_fee_per_gas = min(int(tx['maxFeePerGas'] * self.bump_ratio), 2 * base_fee_per_gas + max_priority_fee_per_gas)
        tx['maxPriorityFeePerGas'] = max_priority_fee_per_gas
        tx['maxFeePerGas'] = max_fee_per_gas


def get_error_message(tx_hash):
    try:
        tx = w3.eth.get_transaction(tx_hash)
        replay_tx = {
            'to': tx['to'],
            'from': tx['from'],
            'value': tx['value'],
            'data': tx.get('data') or tx.get('input'),
        }
        w3.eth.call(replay_tx)
    except ValueError as e:
        if len(e.args) != 1:
            return None
        data = e.args[0]
        if type(data) == str:
            return data
        elif type(data) == dict:
            return data.get('message')
    except:
        return None
    return None


def send_and_wait_tx_status(tx, pk, gas_strategy, tx_name=""):
    gas_strategy.fill_initial_gas_fees(tx)
    while tx['maxPriorityFeePerGas'] < PRIORITY_FEE_PER_GAS_LIMIT:
        # Sign tx:
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=pk)
        tx_hash = w3.toHex(w3.keccak(signed_tx.rawTransaction))
        tx_name_str = f"({tx_name}) " if tx_name else " "
        # Send tx:
        if cmd_args.mainnet:
            log(f"Sending tx {tx_name_str}to {WEB3_PRIVATE_ENDPOINT} privately...")
            w3_private.eth.send_raw_transaction(signed_tx.rawTransaction)
            try:
                log(f"Sending tx {tx_name_str} to backup endpoint...")
                w3_backup.eth.send_raw_transaction(signed_tx.rawTransaction)
            except Exception as e:
                log(f"Failed to send tx {tx_name_str} to backup endpoint...")
        else:
            log(f"Sending tx {tx_name_str}to mempool...")
            w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        # Wait tx status:
        log(f"Transaction {tx_hash} {tx_name_str}was sent. Waiting for confirmation...")
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            is_ok = receipt["status"] == 1
            error_message = None
            if not is_ok:
                error_message = get_error_message(tx_hash)
            log(f"Transaction {tx_hash} {tx_name_str}{'succeeded' if is_ok else 'reverted'}")
            return is_ok, error_message
        except Exception as e:
            log(f"Transaction {tx_hash} {tx_name_str}was not included: {e}. Increasing priority fee...")
            gas_strategy.fill_next_gas_fees(tx)
    log(f"Reached maximum priority fee. Finishing loop...")
    return False, None


def now_time():
    if cmd_args.mainnet:
        return int(time.time())
    return w3.eth.getBlock('latest').timestamp + 120


class GammaFarmBot:
    def __init__(self, min_epoch_duration, min_period_before_emergency_recover):
        assert isinstance(min_epoch_duration, timedelta), "min_epoch_duration must be timedelta"
        assert isinstance(min_period_before_emergency_recover, timedelta), "min_period_before_emergency_recover must be timedelta"
        self.min_epoch_duration = min_epoch_duration
        self.min_period_before_emergency_recover = min_period_before_emergency_recover
        # Initialize contracts:
        self.gamma_farm = w3.eth.contract(address=GAMMA_FARM_ADDRESS, abi=GAMMA_FARM_ABI)
        self.lqty = w3.eth.contract(address=LQTY_ADDRESS, abi=ERC20_ABI)
        # Initialize helpers:
        self.epoch_trade_helper = EpochTradeHelper(w3)
        self.liquity_helper = LiquityHelper(w3)
        self.price_provider = PriceProvider()
        self.last_emergency_condition_ts = now_time()
        # Prompt password for keyfile:
        gamma_farm_owner_address = self.gamma_farm.functions.owner().call()
        if cmd_args.mainnet:
            pk = getpass(f"Enter private key for GammaFarm owner account ({gamma_farm_owner_address}):\n")
        else:
            pk = "0x6c46d4ed5bb1667797867b00773e7cb52a048dccad5da7338c646c3d91d2b19d"
        self.gamma_farm_owner = w3.eth.account.privateKeyToAccount(pk)
        assert self.gamma_farm_owner.address == gamma_farm_owner_address

    def sigint_handler(self, signum, frame):
        log('Received SIGINT. Terminating...')
        signal.signal(signum, signal.SIG_IGN)
        sys.exit(0)

    # --- GammaFarm methods ---

    def start_new_epoch(self):
        # Check current gas price:
        base_fee_per_gas = w3.eth.getBlock('pending').baseFeePerGas
        if base_fee_per_gas > BASE_FEE_PER_GAS_LIMIT:
            log(f"Base fee is too high: {base_fee_per_gas} > {BASE_FEE_PER_GAS_LIMIT}, skipping...")
            return False, "Base fee is too high"
        # Build trade data:
        trade_data = self.build_epoch_trade_data()
        # Build start new epoch tx:
        start_new_epoch_func = self.gamma_farm.functions.startNewEpoch(trade_data)
        tx = start_new_epoch_func.buildTransaction({
            'from': self.gamma_farm_owner.address,
            'nonce': w3.eth.getTransactionCount(self.gamma_farm_owner.address),
            'gas': START_NEW_EPOCH_GAS_LIMIT,
        })
        gas_strategy = GasStrategy(
            initial_max_base_fee_per_gas_ratio=0.5,
            initial_max_priority_fee_per_gas=w3.toWei('1', 'gwei')
        )
        pk = self.gamma_farm_owner.privateKey
        is_ok, error_msg = send_and_wait_tx_status(tx, pk, gas_strategy, tx_name='startNewEpoch')
        return is_ok, error_msg

    def emergency_withdraw(self):
        # Build trade data:
        trade_data = self.build_epoch_trade_data()
        # Build emergencyWithdraw tx
        emergency_withdraw_func = self.gamma_farm.functions.emergencyWithdraw(trade_data)
        tx = emergency_withdraw_func.buildTransaction({
            'from': self.gamma_farm_owner.address,
            'nonce': w3.eth.getTransactionCount(self.gamma_farm_owner.address),
            'gas': EMERGENCY_WITHDRAW_GAS_LIMIT,
        })
        gas_strategy = GasStrategy(
            initial_max_base_fee_per_gas_ratio=2,
            initial_max_priority_fee_per_gas=w3.toWei('2', 'gwei')
        )
        pk = self.gamma_farm_owner.privateKey
        is_ok, error_msg = send_and_wait_tx_status(tx, pk, gas_strategy, tx_name='emergencyWithdraw')
        return is_ok, error_msg

    def emergency_recover(self):
        # Build emergencyRecover tx
        emergency_recover_func = self.gamma_farm.functions.emergencyRecover()
        tx = emergency_recover_func.buildTransaction({
            'from': self.gamma_farm_owner.address,
            'nonce': w3.eth.getTransactionCount(self.gamma_farm_owner.address),
            'gas': EMERGENCY_RECOVER_GAS_LIMIT,
        })
        gas_strategy = GasStrategy(
            initial_max_base_fee_per_gas_ratio=0.5,
            initial_max_priority_fee_per_gas=w3.toWei('1', 'gwei')
        )
        pk = self.gamma_farm_owner.privateKey
        is_ok, error_msg = send_and_wait_tx_status(tx, pk, gas_strategy, tx_name='emergencyRecover')
        return is_ok, error_msg

    def get_farm_emergency_state(self):
        return self.gamma_farm.functions.isEmergencyState().call()

    # --- Epoch and emergency tracking helpers ---

    def estimate_gains(self):
        (eth_gain, lqty_gain) = self.liquity_helper.estimate_gains(GAMMA_FARM_ADDRESS, now_time())
        eth_gain += w3.eth.getBalance(GAMMA_FARM_ADDRESS)
        lqty_gain += self.lqty.functions.balanceOf(GAMMA_FARM_ADDRESS).call()
        return (eth_gain, lqty_gain)

    def build_epoch_trade_data(self):
        (eth_gain, lqty_gain) = self.estimate_gains()
        if eth_gain == 0 and lqty_gain == 0:
            return b''
        mal_burn_pct = self.gamma_farm.functions.malBurnPct().call()
        trade_data = self.epoch_trade_helper.build_trade_data(eth_gain, lqty_gain, mal_burn_pct)
        return trade_data

    def evaluate_emergency_condition(self):
        # Signals:
        eth_price = self.price_provider.get_eth_price()
        lusd_price = self.price_provider.get_lusd_price()
        (undercoll_eth_price, oracle_last_eth_price, last_lowest_ICR, last_TCR, new_lowest_ICR, new_TCR) = \
            self.liquity_helper.calculate_emergency_signals(eth_price)
        # For a given ETH price, define emergency condition as true, if:
        # - price puts system in recovery mode (TCR < CCR) or creates undercoll troves (ICR < MCR)
        # - LUSD price is at least LUSD_MIN_EMERGENCY_PRICE (1.02)
        is_emergency_oracle_price = (last_lowest_ICR < MCR or last_TCR < CCR)
        is_emergency_new_price = (new_lowest_ICR < MCR or new_TCR < CCR) and lusd_price >= LUSD_MIN_EMERGENCY_PRICE
        log(f"Emergency evaluation: " + \
            f"is_emergency_oracle={is_emergency_oracle_price}, is_emergency_new={is_emergency_new_price} | " + \
            f"lusd=${lusd_price}, liquidation_eth=${undercoll_eth_price}, " + \
            f"oracle_last_eth=${oracle_last_eth_price}, coinbase_eth=${eth_price}, " + \
            f"last_TCR={last_TCR}, new_TCR={new_TCR}, last_min_ICR={last_lowest_ICR}, new_min_ICR={new_lowest_ICR}")
        return (is_emergency_oracle_price, is_emergency_new_price)

    # --- Trigger methods for GammaFarm actions ---

    def should_emergency_withdraw(self):
        (is_emergency_oracle_price, is_emergency_new_price) = self.evaluate_emergency_condition()
        if is_emergency_oracle_price or is_emergency_new_price:
            self.last_emergency_condition_ts = now_time()
        # Decision: withdraw, if:
        # - system is not in emergency condition as of last oracle price
        # - system is in emergency condition as of new price
        should_withdraw = not is_emergency_oracle_price and is_emergency_new_price
        log(f"Should emergency withdraw: {'YES' if should_withdraw else 'NO'}")
        return should_withdraw

    def should_emergency_recover(self):
        (is_emergency_oracle_price, is_emergency_new_price) = self.evaluate_emergency_condition()
        if is_emergency_oracle_price or is_emergency_new_price:
            self.last_emergency_condition_ts = now_time()
        # Decision: recover, if:
        # - system is not in emergency condition for the last "min_period_before_emergency_recover"
        seconds_since_last_emergency = now_time() - self.last_emergency_condition_ts
        should_recover = seconds_since_last_emergency >= self.min_period_before_emergency_recover.total_seconds()
        log(f"Should emergency recover: {'YES' if should_recover else 'NO'}")
        return should_recover

    def should_start_new_epoch(self):
        # Check time since start of current epoch:
        epoch_start_time = self.gamma_farm.functions.epochStartTime().call()
        epoch_duration_secs = now_time() - epoch_start_time
        if epoch_duration_secs < self.min_epoch_duration.total_seconds():
            log(f"Too early for new epoch (elapsed={epoch_duration_secs}s), skipping...")
            return False
        # Check whether there are funds:
        (total_lusd, _) = self.gamma_farm.functions.getTotalBalances().call()
        if total_lusd == 0:
            log("No funds in contract, skipping...")
            return False
        return True

    # --- Single run iteration and main run loop ---

    def run_iteration(self):
        # Get current contract emergency state:
        farm_emergency_state = self.get_farm_emergency_state()
        log(f"Farm is {'' if farm_emergency_state else 'not '}in emergency state.")

        # Check if should flip emergency state:
        (should_recover, should_withdraw) = (False, False)
        if farm_emergency_state:
            should_recover = self.should_emergency_recover()
        else:
            should_withdraw = self.should_emergency_withdraw()

        # If needed, perform emergency withdraw or recovery:
        if should_recover:
            self.emergency_recover()
        elif should_withdraw:
            self.emergency_withdraw()

        # Don't start new epoch during emergency or if emergency action taken:
        if farm_emergency_state or (should_recover or should_withdraw):
            return

        log(f"Checking if it's time for new epoch...")
        if not self.should_start_new_epoch():
            return
        # Start new epoch:
        is_ok, error_msg = self.start_new_epoch()
        if is_ok:
            log(f"New epoch has started!")
        else:
            log(f"Failed to start new epoch: {error_msg}")
            if "frontrun protection" in error_msg:
                sleep_mins = random.randint(10, 60)
                log(f"Sleeping for {sleep_mins} mins...")
                time.sleep(sleep_mins * 60)


    def run(self, loop_interval):
        if not cmd_args.mainnet:
            log("Running in development mode... (for mainnet use --mainnet flag)")
        signal.signal(signal.SIGINT, self.sigint_handler)
        assert isinstance(loop_interval, timedelta), "loop_interval must be timedelta"
        while True:
            try:
                log("="*40)
                log("Starting new iteration...")
                self.run_iteration()
            except Exception as e:
                log(f"Exception caught in run loop: {e}")
                log(traceback.format_exc())
            log(f"Iteration finished. Sleeping for {loop_interval.total_seconds()} seconds...")
            time.sleep(loop_interval.total_seconds())


if __name__ == '__main__':
    gamma_farm_bot = GammaFarmBot(
        min_epoch_duration=timedelta(days=2),
        min_period_before_emergency_recover=timedelta(hours=6),
    )
    gamma_farm_bot.run(loop_interval=timedelta(minutes=1))
