from brownie import Contract, accounts
import click

def get_contract_and_account():
    account = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    joint = Contract("0xb3b545dAf579262dA4D232D89E7b7D08AaC23D00")
    providerA = Contract(joint.providerA())
    providerB = Contract(joint.providerB())

    return (account, joint, providerA, providerB)

def setup_hedgil_joint():
    account, joint, providerA, providerB = get_contract_and_account()

    providerA.setJoint(joint, {'from': account})
    providerB.setJoint(joint, {'from': account})

def set_debt_ratios(amountA):
    account, joint, providerA, providerB = get_contract_and_account()
    vaultA = Contract(providerA.vault())
    vaultB = Contract(providerB.vault())

    decimalsA = vaultA.decimals()
    decimalsB = vaultB.decimals()
    DECIMALS_DIFF = 10 ** (decimalsB - decimalsA)
    if(decimalsA > decimalsB):
        DECIMALS_DIFF = 10 ** (decimalsA - decimalsB)

    pair = Contract(joint.pair())
    if(providerA.address > providerB.address):
        (reserveB, reserveA, l) = pair.getReserves()
    else:
        (reserveA, reserveB, l) = pair.getReserves()

    amountB = amountA * reserveB / reserveA * DECIMALS_DIFF * (1+joint.hedgeBudget() / 10_000)
    print(f"Depositing {amountA/10**decimalsA} tokenA")
    print(f"Depositing {amountB/10**decimalsB} tokenB")
    debtRatioA = amountA/vaultA.totalAssets() * 10_000
    debtRatioB = amountB/vaultB.totalAssets() * 10_000

    vaultA.updateStrategyDebtRatio(providerA, debtRatioA, {'from': account})
    vaultB.updateStrategyDebtRatio(providerB, debtRatioB, {'from': account})

def init_epoch():
    account, joint, providerA, providerB = get_contract_and_account()

    providerA.setTakeProfit(False, {'from': account})
    providerB.setTakeProfit(False, {'from': account})
    providerA.setInvestWant(True, {'from': account})
    providerB.setInvestWant(True, {'from': account})

    joint.setHedgingEnabled(True, False, {'from': account})
    joint.setHedgeBudget(50, {'from': account})
    joint.setHedgingPeriod(2 * 24 * 3600, {'from': account})
    joint.setProtectionRange(1500, {'from': account})

    amountA = 0 # amountB will be setted accordingly
    set_debt_ratios(amountA)

    harvest_providers(providerA, providerB, account)

def finish_epoch():
    account, joint, providerA, providerB = get_contract_and_account()

    # set debt ratios to 0
    set_debt_ratios(0)

    # remove hedge budget to force set up at init epoch
    joint.setHedgeBudget(0, {'from': account})

    providerA.setTakeProfit(True, {'from': account})
    providerB.setTakeProfit(True, {'from': account})
    providerA.setInvestWant(False, {'from': account})
    providerB.setInvestWant(False, {'from': account})

    harvest_providers(providerA, providerB, account)

def harvest_providers(providerA, providerB, account):
    providerA.harvest({'from:': account})
    providerB.harvest({'from:': account})