import json
import time
from web3 import Web3

COMMUNITY_ISSUANCE_ADDRESS = "0xD8c9D9071123a059C6E0A945cF0e0c82b508d816"
LUSD_STABILITY_POOL_ADDRESS = "0x66017D22b0f8556afDd19FC67041899Eb65a21bb"
PRICE_FEED_ADDRESS = "0x4c517D4e2C851CA76d7eC94B805269Df0f2201De"
SORTED_TROVES_ADDRESS = "0x8FdD3fbFEb32b28fb73555518f8b361bCeA741A6"
TROVE_MANAGER_ADDRESS = "0xA39739EF8b0231DbFA0DcdA07d7e29faAbCf4bb2"

COMMUNITY_ISSUANCE_ABI = json.loads(open(f"abi/CommunityIssuance.json", "r").read())
LUSD_STABILITY_POOL_ABI = json.loads(open(f"abi/LUSDStabilityPool.json", "r").read())
PRICE_FEED_ABI = json.loads(open(f"abi/PriceFeed.json", "r").read())
SORTED_TROVES_ABI = json.loads(open(f"abi/SortedTroves.json", "r").read())
TROVE_MANAGER_ABI = json.loads(open(f"abi/TroveManager.json", "r").read())

MCR = 1.1  # Minimum Collateral Ratio
CCR = 1.5  # Critical Collateral Ratio


class LiquityHelper:
    def __init__(self, w3):
        self.w3 = w3
        # Initialize contracts:
        self.lqty_comm_issuance = w3.eth.contract(address=COMMUNITY_ISSUANCE_ADDRESS, abi=COMMUNITY_ISSUANCE_ABI)
        self.lusd_stability_pool = w3.eth.contract(address=LUSD_STABILITY_POOL_ADDRESS, abi=LUSD_STABILITY_POOL_ABI)
        self.price_feed = w3.eth.contract(address=PRICE_FEED_ADDRESS, abi=PRICE_FEED_ABI)
        self.sorted_troves = w3.eth.contract(address=SORTED_TROVES_ADDRESS, abi=SORTED_TROVES_ABI)
        self.trove_manager = w3.eth.contract(address=TROVE_MANAGER_ADDRESS, abi=TROVE_MANAGER_ABI)

    def get_price_feed_last_good_price(self):
        return self.price_feed.functions.lastGoodPrice().call() / 1e18

    def get_total_amounts(self):
        total_eth_coll = self.trove_manager.functions.getEntireSystemColl().call()
        total_lusd_debt = self.trove_manager.functions.getEntireSystemDebt().call()
        return (total_eth_coll, total_lusd_debt)

    def get_trove_amounts(self, borrower):
        pending_eth_reward = self.trove_manager.functions.getPendingETHReward(borrower).call()
        pending_lusd_debt_reward = self.trove_manager.functions.getPendingLUSDDebtReward(borrower).call()
        # struct Trove {debt, coll, stake, status, arrayIndex}
        (debt, coll, _, _, _) = self.trove_manager.functions.Troves(borrower).call()
        current_eth_coll = coll + pending_eth_reward
        current_lusd_debt = debt + pending_lusd_debt_reward
        return (current_eth_coll, current_lusd_debt)

    def get_lowest_trove_amounts(self):
        lowest_trove = self.sorted_troves.functions.getLast().call()
        (eth_coll, lusd_debt) = self.get_trove_amounts(lowest_trove)
        return (eth_coll, lusd_debt)

    # Calculate Ether price to undercollateralize at least one Liquity trove
    def calculate_undercoll_eth_price(self):
        # Find price such that ICR < MCR i.e. (eth_coll * price / lusd_debt) < MCR
        (eth_coll, lusd_debt) = self.get_lowest_trove_amounts()
        eth_price = MCR * lusd_debt / eth_coll
        return eth_price

    # Calculate Liquity system TCR, given eth_price
    def calculate_TCR(self, eth_price):
        return self.trove_manager.functions.getTCR(int(eth_price * 1e18)).call() / 1e18

    # Check if Liquity system would be in Recovery Mode, given eth_price
    def check_recovery_mode(self, eth_price):
        return self.trove_manager.functions.checkRecoveryMode(int(eth_price * 1e18)).call()

    def calculate_emergency_signals(self, eth_price):
        oracle_last_eth_price = self.get_price_feed_last_good_price()
        (trove_eth_coll, trove_lusd_debt) = self.get_lowest_trove_amounts()
        undercoll_eth_price = MCR * trove_lusd_debt / trove_eth_coll
        # ICR and recovery_mode check with last oracle price:
        last_lowest_ICR = trove_eth_coll * oracle_last_eth_price / trove_lusd_debt
        last_TCR = self.calculate_TCR(oracle_last_eth_price)
        # ICR and recover_mode check with current price:
        lowest_ICR = trove_eth_coll * eth_price / trove_lusd_debt
        TCR = self.calculate_TCR(eth_price)
        return (undercoll_eth_price, oracle_last_eth_price, last_lowest_ICR, last_TCR, lowest_ICR, TCR)

    # --- LQTY/ETH rewards methods ---

    def estimate_pending_lqty_gain(self, depositor, now_ts=None):
        lusd_sp = self.lusd_stability_pool
        initial_deposit = lusd_sp.functions.deposits(depositor).call()[0]
        if initial_deposit == 0:
            return 0
        LQTY_ISSUANCE_DEPLOYMENT_TIME = 1617611537
        LQTY_ISSUANCE_FACTOR = 999998681227695000
        LQTY_SUPPLY_CAP = 32 * 10**24
        SCALE_FACTOR = 10**9
        # 1. issueLQTY():
        now_ts = now_ts or int(time.time())
        mins = (now_ts - LQTY_ISSUANCE_DEPLOYMENT_TIME) // 60
        cum_fr = 10**18 - self._dec_pow(LQTY_ISSUANCE_FACTOR, mins)
        total_lqty_issued = self.lqty_comm_issuance.functions.totalLQTYIssued().call()
        new_total_lqty_issued = LQTY_SUPPLY_CAP * cum_fr // 10**18
        new_lqty_issued = new_total_lqty_issued - total_lqty_issued
        # 2. updateG():
        total_lusd = lusd_sp.functions.getTotalLUSDDeposits().call()
        last_lqty_error = lusd_sp.functions.lastLQTYError().call()
        lqty_per_unit_staked = (new_lqty_issued * 10**18 + last_lqty_error) // total_lusd
        marginal_lqty_gain = lqty_per_unit_staked * lusd_sp.functions.P().call()
        cur_epoch = lusd_sp.functions.currentEpoch().call()
        cur_scale = lusd_sp.functions.currentScale().call()
        # 3. getDepositorLQTYGain():
        (S, P, G, scale, epoch) = lusd_sp.functions.depositSnapshots(depositor).call()
        epochScaleG = lusd_sp.functions.epochToScaleToG(epoch, scale).call()
        epochNextScaleG = lusd_sp.functions.epochToScaleToG(epoch, scale + 1).call()
        epochScaleG += marginal_lqty_gain if (cur_epoch == epoch and cur_scale == scale) else 0
        epochNextScaleG += marginal_lqty_gain if (cur_epoch == epoch and cur_scale == scale + 1) else 0
        q1 = epochScaleG - G
        q2 = epochNextScaleG // SCALE_FACTOR
        lqty_gain = initial_deposit * (q1 + q2) // P // 10**18
        return lqty_gain

    def estimate_gains(self, depositor, now_ts=None):
        lqty_gain = self.estimate_pending_lqty_gain(depositor, now_ts)
        eth_gain = self.lusd_stability_pool.functions.getDepositorETHGain(depositor).call()
        return (eth_gain, lqty_gain)

    # --- LiquityMath methods ---

    def _dec_pow(self, base, mins):
        if mins > 525600000:
            return 525600000
        if mins == 0:
            return 10**18
        y = 10**18
        x = base
        n = mins
        while n > 1:
            if n % 2 == 0:
                x = self._dec_mul(x, x)
                n = n // 2
            else:
                y = self._dec_mul(x, y)
                x = self._dec_mul(x, x)
                n = (n - 1) // 2
        return self._dec_mul(x, y)

    def _dec_mul(self, x, y):
        return (x * y + 10**18 // 2) // 10**18
