from brownie import accounts, Contract
from brownie.exceptions import RPCRequestError
from brownie.network.transaction import Status as TxStatus
from scripts.common import deposit, get_console_logs, DEBUG, E18, LUSD_STABILITY_POOL_ADDRESS
from scripts.simulation.structs import EventType, SimulationState
from scripts.tokens import LUSD_ADDRESS, LUSD_HOLDER, MAL_ADDRESS, MAL_HOLDER, token_contract

from collections import defaultdict
from eth_abi import encode_abi

import os
import threading
import time


class PremineChainHelper:
    def __init__(self, chain, history):
        self.chain = chain
        self.history = history
        self.priority_fee = int(2e9)
        self._check_network_settings()

    def deploy_contract(self, obj, args=[], deployer=None):
        def mine_block():
            while len(self.history) == 0 or self.history[-1].status != TxStatus.Pending:
                time.sleep(1)
            self.chain.mine()
        threading.Thread(target=mine_block, args=()).start()
        contract = obj.deploy(*args, {'from': deployer or accounts[0]})
        return contract

    def mine_block(self, txs, ts=None, check_order=False, allow_revert=False):
        try:
            self.chain.mine(timestamp=ts)
        except RPCRequestError as e:
            if not allow_revert or "revert" not in str(e):
                raise e
        finally:
            [tx.wait(1) for tx in txs]
        if check_order:
            for i in range(len(txs)):
                assert txs[i].txindex == i

    def tx_args(self, tx_args_={}):
        tx_args = {
            'max_fee': self.chain.base_fee * 2 + self.priority_fee,
            'priority_fee': self.priority_fee,
            'required_confs': 0,
        }
        tx_args |= tx_args_
        self.priority_fee -= 1
        return tx_args

    def _check_network_settings(self):
        from brownie import network
        from brownie._config import CONFIG
        assert network.show_active() == "mainnet-fork"
        block_time = CONFIG.networks['mainnet-fork']['cmd_settings'].get('block_time')
        assert block_time is not None and block_time > 0, "can not use with instamine"


class GammaFarmSimulator:
    def __init__(self, chain, history, mal_to_distribute, mal_distribution_period_secs, mal_reward_per_sec, mal_decay_factor, mal_decay_period_secs=86400, use_prod_lusd_sp=False, debug=False):
        self.pch = PremineChainHelper(chain, history)
        self.chain = chain
        self.history = history
        # Initialize contracts:
        from brownie import TestGammaFarm, TestStabilityPool
        self.owner = accounts[5]
        if use_prod_lusd_sp:
            self.lusd_sp = Contract(LUSD_STABILITY_POOL_ADDRESS)
        else:
            self.lusd_sp = self.pch.deploy_contract(TestStabilityPool)
        self.gamma_farm = self.pch.deploy_contract(
            TestGammaFarm,
            args=[
                mal_to_distribute,
                mal_distribution_period_secs,
                mal_reward_per_sec,
                mal_decay_factor,
                mal_decay_period_secs,
                self.lusd_sp.address,
            ],
            deployer=self.owner,
        )
        self.start_ts = self.gamma_farm.epochStartTime()
        self.lusd = token_contract(LUSD_ADDRESS)
        self.mal = token_contract(MAL_ADDRESS)
        self.users = set()
        self.user_lusd_in = defaultdict(lambda: 0)
        self.user_lusd_out = defaultdict(lambda: 0)
        self.user_mal_out = defaultdict(lambda: 0)
        self.total_lusd_reward = 0
        self.total_lusd_sp_loss = 0
        self.user_gas_used = defaultdict(lambda: 0)
        self.owner_gas_used = 0
        # Fund GammaFarm with MAL:
        transfer_tx1 = accounts[0].transfer(LUSD_HOLDER, 10*E18, required_confs=0)
        transfer_tx2 = accounts[0].transfer(MAL_HOLDER, E18, required_confs=0)
        self.pch.mine_block([transfer_tx1, transfer_tx2], ts=self.start_ts)
        fund_mal_tx = self.mal.transfer(self.gamma_farm.address, mal_to_distribute, self.pch.tx_args({'from': MAL_HOLDER}))
        self.pch.mine_block([fund_mal_tx], ts=self.start_ts)
        # debug:
        self.debug = debug or DEBUG
        if self.debug:
            dir = f"{'/'.join(os.path.realpath(__file__).split('/')[0:-3])}/logs"
            os.makedirs(dir, exist_ok=True)
            self.fout = open(f"{dir}/log_sim.txt", "w")

    def simulate_events(self, events):
        self._fund_users(events)
        for e in events:
            self.simulate_event(e)
        return self.gather_state()

    def simulate_event(self, e):
        if e.user is not None:
            self.users.add(e.user)
        ts = self.start_ts + e.ts
        if e.type == EventType.DEPOSIT:
            if self.lusd.balanceOf(accounts[e.user]) < e.amount:
                self._fund_user(e.user, e.amount, ts)
            self.user_lusd_in[e.user] += e.amount
            tx = deposit(accounts[e.user], e.amount, self.gamma_farm, tx_args=self.pch.tx_args())
        elif e.type == EventType.WITHDRAW:
            tx = self.gamma_farm.withdraw(self.pch.tx_args({'from': accounts[e.user]}))
        elif e.type == EventType.UNSTAKE:
            tx = self.gamma_farm.unstake(self.pch.tx_args({'from': accounts[e.user]}))
        elif e.type == EventType.UNSTAKE_AND_WITHDRAW:
            data = self._mock_epoch_reward_and_loss(e, ts)
            tx = self.gamma_farm.unstakeAndWithdraw(self.pch.tx_args({'from': accounts[e.user]}))
        elif e.type == EventType.CLAIM:
            tx = self.gamma_farm.claim(self.pch.tx_args({'from': accounts[e.user]}))
        elif e.type == EventType.NEW_EPOCH:
            data = self._mock_epoch_reward_and_loss(e, ts)
            tx = self.gamma_farm.startNewEpoch(data, self.pch.tx_args({'from': self.owner}))
        elif e.type == EventType.EMERGENCY_WITHDRAW:
            data = self._mock_epoch_reward_and_loss(e, ts)
            tx = self.gamma_farm.emergencyWithdraw(data, self.pch.tx_args({'from': self.owner}))
        elif e.type == EventType.EMERGENCY_RECOVER:
            tx = self.gamma_farm.emergencyRecover(self.pch.tx_args({'from': self.owner}))
        else:
            raise Exception(f"Unknown event type: {e.type}")
        # Mine block:
        self.pch.mine_block([tx], ts=ts)
        if e.type == EventType.WITHDRAW or e.type == EventType.UNSTAKE_AND_WITHDRAW:
            self.user_lusd_out[e.user] += int(tx.return_value)
        # Gas used:
        if e.user is not None:
            self.user_gas_used[e.user] += tx.gas_used
        else:
            self.owner_gas_used += tx.gas_used
        if self.debug:
            self.fout.write(f"=========\n* {e}\n")
            self.fout.write(f"Gas used: {tx.gas_used}\n")
            logs = get_console_logs(tx)
            if logs:
                self.fout.write("\n".join([str(v) for v in logs]) + "\n")
            self.fout.flush()
        return tx

    def gather_state(self):
        s = SimulationState()
        s.users = self.users
        for user in self.users:
            address = accounts[user]
            s.userLusdIn[user] = self.user_lusd_in[user]
            s.userLusdOut[user] = self.user_lusd_out[user]
            s.userMalOut[user] = self.mal.balanceOf(address)
            (s.lusdAvailable[user], s.lusdStaked[user], s.malRewards[user], _, _) = \
                self.gamma_farm.getAccountBalances(address)
        (s.totalLusd, s.totalLusdStaked) = self.gamma_farm.getTotalBalances()
        (s.P, s.S2, s.S1) = self.gamma_farm.getLastSnapshot()
        s.epoch = self.gamma_farm.epoch()
        s.totalUserLusdIn = sum(s.userLusdIn.values())
        s.totalUserLusdOut = sum(s.userLusdOut.values())
        s.totalMalSupply = self.gamma_farm.malToDistribute()
        s.totalMalOut = sum(s.userMalOut.values())
        s.totalLusdReward = self.total_lusd_reward
        s.totalLusdSpLoss = self.total_lusd_sp_loss
        s.farmLusdBalance = self.lusd.balanceOf(self.gamma_farm.address)
        s.farmMalBalance = self.mal.balanceOf(self.gamma_farm.address)
        s.spCompoundedDeposit = self.lusd_sp.getCompoundedLUSDDeposit(self.gamma_farm.address)
        assert s.farmLusdBalance == s.totalUserLusdIn + s.totalLusdReward - s.totalLusdSpLoss - s.totalUserLusdOut - s.spCompoundedDeposit
        assert s.farmMalBalance == s.totalMalSupply - s.totalMalOut
        assert s.spCompoundedDeposit == s.totalLusdStaked
        assert sum(s.malRewards.values()) + s.totalMalOut <= s.totalMalSupply
        return s

    def get_total_balances(self):
        return self.gamma_farm.getTotalBalances()

    def get_account_balances(self, user):
        return self.gamma_farm.getAccountBalances(accounts[user])

    def get_total_gas_used(self):
        return (sum(self.user_gas_used.values()), self.owner_gas_used)

    def _fund_users(self, events):
        # Fund users:
        user_amounts = defaultdict(lambda: 0)
        for e in events:
            if e.type == EventType.DEPOSIT:
                user_amounts[e.user] += e.amount
        fund_txs = []
        for user in user_amounts:
            fund_tx = self.lusd.transfer(accounts[user], user_amounts[user], self.pch.tx_args({'from': LUSD_HOLDER}))
            fund_txs.append(fund_tx)
        self.pch.mine_block(fund_txs, ts=self.start_ts)

    def _fund_user(self, user, amount, ts):
        fund_tx = self.lusd.transfer(accounts[user], amount, self.pch.tx_args({'from': LUSD_HOLDER}))
        self.pch.mine_block([fund_tx], ts=ts)

    def _mock_epoch_reward_and_loss(self, e, ts):
        if self.lusd_sp.address == LUSD_STABILITY_POOL_ADDRESS:
            return b''
        lusd_sp_staked_before = self.lusd_sp.getCompoundedLUSDDeposit(self.gamma_farm.address)
        (lusd_reward, lusd_sp_staked_after) = e.data.get_epoch_results(lusd_sp_staked_before)
        # Mock SP loss and send LUSD "reward" to GammaFarm:
        tx1 = self.lusd_sp.setCompoundedLUSDDeposit(lusd_sp_staked_after, self.pch.tx_args({'from': accounts[0]}))
        tx2 = self.lusd.transfer(self.gamma_farm, lusd_reward, self.pch.tx_args({'from': LUSD_HOLDER}))
        self.pch.mine_block([tx1, tx2], ts=ts)
        # Encode data:
        self.total_lusd_reward += lusd_reward
        self.total_lusd_sp_loss += (lusd_sp_staked_before - lusd_sp_staked_after)
        reward_data = encode_abi(['uint256'], [lusd_reward])
        return reward_data