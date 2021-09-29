from brownie import Contract, accounts, chain, history
import click

dict = {
    "ETH-USDC": Contract("0x7023Ae05e0FD6f7d6C7BbCB8b435BaF065Df3acD"),
    "WBTC-USDC": Contract("0x7023Ae05e0FD6f7d6C7BbCB8b435BaF065Df3acD"),
}
joint = dict[click.prompt("Joint", type=click.Choice(list(dict.keys())))]
# account = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))


def get_contract_and_account():
    account = accounts.at("0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7", force=True)
    providerA = Contract(joint.providerA())
    providerB = Contract(joint.providerB())

    return (account, joint, providerA, providerB)


def setup_hedgil_joint():
    account, joint, providerA, providerB = get_contract_and_account()

    providerA.setJoint(joint, {"from": account})
    providerB.setJoint(joint, {"from": account})


def set_debt_ratios(zero=False):
    account, joint, providerA, providerB = get_contract_and_account()
    vaultA = Contract(providerA.vault())
    vaultB = Contract(providerB.vault())

    decimalsA = vaultA.decimals()
    decimalsB = vaultB.decimals()
    DECIMALS_DIFF = 1
    if decimalsA > decimalsB:
        DECIMALS_DIFF = 10 ** (decimalsA - decimalsB)
    else:
        DECIMALS_DIFF = 10 ** (decimalsB - decimalsA)

    print(f"decimals: A: {decimalsA}, B: {decimalsB}, diff: {DECIMALS_DIFF}")
    pair = Contract(joint.pair())
    if providerA.want() > providerB.want():
        (reserveB, reserveA, l) = pair.getReserves()
    else:
        (reserveA, reserveB, l) = pair.getReserves()

    freeRatioA = 10_000 - vaultA.debtRatio()
    freeRatioB = 10_000 - vaultB.debtRatio()
    looseAmountA = vaultA.totalAssets() - vaultA.totalDebt()
    looseAmountB = vaultB.totalAssets() - vaultB.totalDebt()

    availableA = freeRatioA / 10_000 * vaultA.totalAssets()
    availableB = freeRatioB / 10_000 * vaultB.totalAssets()

    availableA = availableA if looseAmountA > availableA else looseAmountA
    availableB = availableB if looseAmountB > availableB else looseAmountB

    print(f"Reserve USDC: {reserveA}")
    print(f"Reserve WETH: {reserveB}")

    print(f"Available USDC: {availableA}")
    print(
        f"Available WETH: {availableB} ({availableB * reserveA * DECIMALS_DIFF / reserveB / (10 ** decimalsB) } USDC)"
    )

    if availableA * DECIMALS_DIFF > availableB * reserveA * DECIMALS_DIFF / reserveB:
        amountB = availableB  ## take all funds available
        amountA = amountB * reserveA / reserveB * (1 + joint.hedgeBudget() / 10_000)
    else:
        amountA = availableA  ## take all funds available
        amountB = amountA * reserveB / reserveA / (1 + joint.hedgeBudget() / 10_000)

    if zero:
        amountA = 0
        amountB = 0

    print(f"Depositing {amountA/10**decimalsA} tokenA")
    print(f"Depositing {amountB/10**decimalsB} tokenB")
    assert amountA <= looseAmountA
    assert amountB <= looseAmountB

    debtRatioA = amountA / vaultA.totalAssets() * 10000
    debtRatioB = amountB / vaultB.totalAssets() * 10000
    print(f"setting {debtRatioA/100}% tokenA")
    print(f"setting {debtRatioB/100}% tokenB")

    vaultA.updateStrategyDebtRatio(providerA, debtRatioA, {"from": account})
    vaultB.updateStrategyDebtRatio(providerB, debtRatioB, {"from": account})


def init_epoch():
    account, joint, providerA, providerB = get_contract_and_account()

    providerA.setTakeProfit(False, {"from": account})
    providerB.setTakeProfit(False, {"from": account})
    providerA.setInvestWant(True, {"from": account})
    providerB.setInvestWant(True, {"from": account})

    budget = 0.50  #%
    joint.setHedgeBudget(budget * 100, {"from": account})
    days = 2  # days
    joint.setHedgingPeriod(days * 24 * 3600, {"from": account})
    protectionRange = 15  #%
    joint.setProtectionRange(protectionRange * 100, {"from": account})

    set_debt_ratios()

    harvest_providers(providerA, providerB, account)
    print_status()


def finish_epoch():
    account, joint, providerA, providerB = get_contract_and_account()

    # set debt ratios to 0
    set_debt_ratios(True)

    # remove hedge budget to force set up at init epoch
    joint.setHedgeBudget(0, {"from": account})

    providerA.setTakeProfit(True, {"from": account})
    providerB.setTakeProfit(True, {"from": account})
    providerA.setInvestWant(False, {"from": account})
    providerB.setInvestWant(False, {"from": account})

    harvest_providers(providerA, providerB, account)

    vaultA = Contract(providerA.vault())
    vaultB = Contract(providerB.vault())

    assert vaultA.strategies(providerA).dict()["totalDebt"] == 0
    assert vaultB.strategies(providerB).dict()["totalDebt"] == 0


def harvest_providers(providerA, providerB, account):
    tx = providerA.harvest({"from": account})
    print(tx.events["Harvested"])
    tx = providerB.harvest({"from": account})
    print(tx.events["Harvested"])


def print_status():
    def print_hedge_status(joint, tokenA, tokenB):
        callID = joint.activeCallID()
        putID = joint.activePutID()
        callProvider = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d")
        putProvider = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b")
        callInfo = callProvider.options(callID)
        putInfo = putProvider.options(putID)
        assert (joint.activeCallID() != 0) & (joint.activePutID() != 0)
        (callPayout, putPayout) = joint.getOptionsProfit()
        print(f"Bought two options:")
        print(f"CALL #{callID}")
        print(f"\tStrike {callInfo[1]/1e8}")
        print(f"\tAmount {callInfo[2]/1e18}")
        print(f"\tTTM {(callInfo[4]-chain.time())/3600}h")
        costCall = (callInfo[5] + callInfo[6]) / 0.8
        print(f"\tCost {(callInfo[5]+callInfo[6])/0.8/1e18} {tokenA.symbol()}")
        print(f"\tPayout: {callPayout/1e18} {tokenA.symbol()}")
        print(f"PUT #{putID}")
        print(f"\tStrike {putInfo[1]/1e8}")
        print(f"\tAmount {putInfo[2]/1e18}")
        print(f"\tTTM {(putInfo[4]-chain.time())/3600}h")
        costPut = (putInfo[5] + putInfo[6]) / 0.8
        print(f"\tCost {costPut/1e6} {tokenB.symbol()}")
        print(f"\tPayout: {putPayout/1e6} {tokenB.symbol()}")
        return (callInfo[1] / 1e8, (callInfo[4] - chain.time()) / 3600)

    pair = Contract(joint.pair())
    (reserve0, reserve1, l) = pair.getReserves()
    providerA = Contract(joint.providerA())
    providerB = Contract(joint.providerB())
    usdc = Contract(joint.tokenA())
    weth = Contract(joint.tokenB())
    vaultA = Contract(providerA.vault())
    vaultB = Contract(providerB.vault())
    totalDebtA = vaultA.strategies(providerA).dict()["totalDebt"]
    totalDebtB = vaultB.strategies(providerB).dict()["totalDebt"]
    currentPrice = reserve0 / reserve1 * 1e12
    balanceA = providerA.balanceOfWant()
    balanceB = providerB.balanceOfWant()
    assetsA = joint.estimatedTotalAssetsInToken(usdc)
    assetsB = joint.estimatedTotalAssetsInToken(weth)
    strategist = providerA.strategist()
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    print(f"InitialA: {totalDebtA/1e6} {usdc.symbol()}")
    print(f"InitialB: {totalDebtB/1e18} {weth.symbol()}")
    initialPrice, ttm = print_hedge_status(joint, weth, usdc)
    providerA.harvest({"from": strategist})
    profitA = history[-1].events["Harvested"]["profit"]
    providerB.harvest({"from": strategist})
    profitB = history[-1].events["Harvested"]["profit"]
    chain.undo(6)

    print(f"CurrentPrice: {currentPrice}")
    print(f"InitialPrice: {initialPrice}")
    print(f"Price change: {(currentPrice/initialPrice-1)*100}%")
    print(f"CurrentBalanceA: {(balanceA+assetsA)/1e6} {usdc.symbol()}")
    print(f"CurrentBalanceB: {(balanceB+assetsB)/1e18} {weth.symbol()}")
    print(f"ReturnA: {profitA/totalDebtA*100*365*24/(7*24-ttm)}%")
    print(f"ReturnB: {profitB/totalDebtB*100*365*24/(7*24-ttm)}%")
