from brownie import accounts, interface, Contract
from brownie.network.account import Account

DAI_ADDRESS = '0x6B175474E89094C44Da98b954EedeAC495271d0F'
LQTY_ADDRESS = '0x6DEA81C8171D0bA574754EF6F8b412F2Ed88c54D'
LUSD_ADDRESS = '0x5f98805A4E8be255a32880FDeC7F6728C6568bA0'
MAL_ADDRESS = '0x6619078Bdd8324E01E9a8D4b3d761b050E5ECF06'
WETH_ADDRESS = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
USDC_ADDRESS = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'

LQTY_HOLDER = '0x32c761138aD9Ff95D8595aa9A79208F19b01d8E7'
LUSD_HOLDER = '0x88Cfdb5B32775940580dC3d34e90Bc8c34f0CF7D'
MAL_HOLDER = '0x90102a92e8E40561f88be66611E5437FEb339e79'
WETH_HOLDER = '0x06920C9fC643De77B99cB7670A944AD31eaAA260'


def fund_lqty(amount_wei=int(1e21), funder=LQTY_HOLDER, fund_to=None):
    _fund(LQTY_ADDRESS, amount_wei=amount_wei, funder=funder, fund_to=fund_to)


def fund_lusd(amount_wei=int(1e21), funder=LUSD_HOLDER, fund_to=None):
    _fund(LUSD_ADDRESS, amount_wei=amount_wei, funder=funder, fund_to=fund_to)


def fund_mal(amount_wei=int(1e21), funder=MAL_HOLDER, fund_to=None):
    _fund(MAL_ADDRESS, amount_wei=amount_wei, funder=funder, fund_to=fund_to)


def fund_weth(amount_wei=int(1e21), funder=WETH_HOLDER, fund_to=None):
    _fund(WETH_ADDRESS, amount_wei=amount_wei, funder=funder, fund_to=fund_to)


def approve_lusd(spender, amount_wei=int(1e23), tx_from=None):
    _approve(LUSD_ADDRESS, amount_wei=amount_wei, spender=spender, tx_from=tx_from)


def approve_lqty(spender, amount_wei=int(1e23), tx_from=None):
    _approve(LQTY_ADDRESS, amount_wei=amount_wei, spender=spender, tx_from=tx_from)


def approve_mal(spender, amount_wei=int(1e23), tx_from=None):
    _approve(MAL_ADDRESS, amount_wei=amount_wei, spender=spender, tx_from=tx_from)


def approve_weth(spender, amount_wei=int(1e23), tx_from=None):
    _approve(WETH_ADDRESS, amount_wei=amount_wei, spender=spender, tx_from=tx_from)


def _fund(token_address, amount_wei, funder, fund_to=None, funder_tx_fee_sponsor=None):
    # Resolve default parameters:
    fund_to = fund_to or accounts[0]
    funder_tx_fee_sponsor = funder_tx_fee_sponsor or accounts[1]
    # Transfer:
    Account(funder_tx_fee_sponsor).transfer(funder, int(10e18))  # transfer 10 ETH to funder to cover tx fee
    token = token_contract(token_address)
    token.transfer(fund_to, amount_wei, {'from': funder})  # transfer amount_wei to fund_to
    print(f'Transfered {amount_wei / 1e18} {token.symbol()} to {fund_to}')


def _approve(token_address, amount_wei, spender, tx_from=None):
    # Resolve default parameters:
    tx_from = tx_from or accounts[0]
    # Approve:
    token = token_contract(token_address)
    token.approve(spender, amount_wei, {'from': tx_from})
    print(f'Approved spending {amount_wei / 1e18} {token.symbol()} to {spender} by {tx_from}')


def token_contract(token_address):
    if token_address == MAL_ADDRESS:
        return interface.ERC20(token_address)
    elif token_address == LUSD_ADDRESS:
        return interface.ILUSDToken(token_address)
    return Contract(token_address)

