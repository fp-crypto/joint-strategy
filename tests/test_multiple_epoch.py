import brownie
import pytest
from brownie import Contract, Wei, chain, interface
from operator import xor
import math
from datetime import datetime


def print_hedge_status(joint, hedgil):
    newhedgil = hedgil.hedgils(joint.activeHedgeID())

    print(f"\n---- Hedgil ---- ")
    print(f"Owner: {newhedgil[0]}")
    print(f"Id: {newhedgil[1]}")
    print(f"Q: {newhedgil[2]}")
    print(f"Strike: {newhedgil[3]}")
    print(f"MaxPriceChange: {newhedgil[4]}")
    print(f"Expiration: {newhedgil[5]}")
    print(f"Cost: {newhedgil[6]}")

    return newhedgil[6]


def sync_price(joint):
    relayer = "0x33E0E07cA86c869adE3fc9DE9126f6C73DAD105e"
    imp = Contract("0x5bfab94edE2f4d911A6CC6d06fdF2d43aD3c7068")

    pair = Contract(joint.pair())
    (reserve0, reserve1, a) = pair.getReserves()
    ftm_price = reserve0 / reserve1 * 1e12 * 10 ** 9
    print(f"Current price is: {ftm_price/1e9}")
    imp.relay(["FTM"], [ftm_price], [chain.time()], [4281375], {"from": relayer})


def test_operation_epoch_1(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    band_oracle,
    hedgil,
):

    print(f"Epoch #1:")
    print(f"Without Hedgil, Without IL. Only to see rewards in ideal conditions:")
    now = datetime.now()
    now_UNIX = int(now.strftime("%s"))
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(False, False, {"from": strategist})
    
    hedgil_budget = 0 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 7 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
        
    # Wait plz
    days_to_sleep_1 = 3
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    #calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    #print(f"IL calculation: {calc_il:,.4f}")
    #print(f"")
    
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    print(f"-----------------------------------------------------------")
    print(f"")


def test_operation_epoch_2(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    band_oracle,
    hedgil,
):    
    
    print(f"Epoch #2:")
    print(f"With Hedgil, With light IL:")
    now = datetime.now()
    now_UNIX = int(now.strftime("%s"))
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A  - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    dump_amountA = 1_200_000 * 1e18
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountA,
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 2
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
        (hedgePayout > 0) & (hedgilInfo[5] == 0)
    )

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    print(f"-----------------------------------------------------------")
    print(f"")
    

def test_operation_epoch_3(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    band_oracle,
    hedgil,
):
    
    print(f"Epoch #3:")
    print(f"Same us Epoch #2, but, harvest is after Hedgil Period:")
    now = datetime.now()
    now_UNIX = int(now.strftime("%s"))
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    dump_amountA = 1_000_000 * 1e18
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountA,
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 3
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    #assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
    #    (hedgePayout > 0) & (hedgilInfo[5] == 0)
    #)

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    #assert lossA == 0
    #assert lossB == 0
    #assert gainA >= 0
    #assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    print(f"-----------------------------------------------------------")
    print(f"")
    

def test_operation_epoch_4(
    chain,
    vaultA,
    vaultB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    providerA,
    providerB,
    joint,
    router,
    gov,
    strategist,
    tokenA_whale,
    tokenB_whale,
    band_oracle,
    hedgil,
):    

    print(f"Epoch #4/1:")
    print(f"With Hedgil, With ligth IL, 4 consecutives epoch:")
    now = datetime.now()
    now_UNIX = int(now.strftime("%s"))
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    dump_amountA = 1_000_000 * 1e18
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountA,
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 2
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
        (hedgePayout > 0) & (hedgilInfo[5] == 0)
    )

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    
    print(f"")
    print(f"Epoch #4/2:")
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    dump_amountB = 1_000_000 * 1e6
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountB,
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 2
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
        (hedgePayout > 0) & (hedgilInfo[5] == 0)
    )

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    
    
    print(f"")
    print(f"Epoch #4/3:")
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    #tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    dump_amountB = 800_000 * 1e6
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountB,
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 2
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
        (hedgePayout > 0) & (hedgilInfo[5] == 0)
    )

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")
    
    print(f"Epoch #4/4:")
    print(f"With Hedgil, With ligth IL, 5 consecutives epoch:")
    now = datetime.now()
    now_UNIX = int(now.strftime("%s"))
    print(f"Time from build 0d, 0h")
    
    sync_price(joint)
    p0 = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {p0}"
    )
    #Hedgil Setup:
    joint.setHedgingEnabled(True, True, {"from": strategist})
    
    hedgil_budget = 0.5 #%
    joint.setHedgeBudget((hedgil_budget*100), {"from": strategist})
    
    hedgil_period = 3 #days
    joint.setHedgingPeriod((hedgil_period*86400), {"from": strategist})
    
    hedgil_price_change = 15 #%
    joint.setProtectionRange((hedgil_price_change*100), {"from": strategist})

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})
    
    #Invest Setup:
    invest_amount_B = 10_000
    invest_amount_A = invest_amount_B / p0
    
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, Wei(f"{invest_amount_A - (hedgil_budget/100)*(invest_amount_B / p0)} ether"), {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, (int(invest_amount_B*1e6)), {"from": gov})
    
    providerA.setTakeProfit(False, {"from": strategist})
    providerB.setTakeProfit(False, {"from": strategist})
    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 9000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 9000, {"from": gov})
    
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    # disabling this bc im paying for options and leaving uninvested funds (< 1%)
    # assert xor(
    #     providerA.balanceOfWant() > 0, providerB.balanceOfWant() > 0
    # )  # exactly one should have some remainder
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    startingA = joint.estimatedTotalAssetsInToken(tokenA)
    startingB = joint.estimatedTotalAssetsInToken(tokenB)
    
    print(f"Provider A debt {vaultA.strategies(providerA).dict()['totalDebt']/1e18:,.2f} {tokenA.symbol()}")
    print(f"Provider B debt {vaultB.strategies(providerB).dict()['totalDebt']/1e6:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerA {providerA.balanceOfWant()/1e18:,.2f} {tokenA.symbol()}")
    print(f"Uninvested in providerB {providerB.balanceOfWant()/1e6:,.2f} {tokenB.symbol()}")
    print(f"Invested in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Invested in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Hedgil cost {(vaultB.strategies(providerB).dict()['totalDebt'] - joint.estimatedTotalAssetsInToken(tokenB) - (providerB.balanceOfWant()))/1e6} {tokenB.symbol()}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost

    # Wait plz
    days_to_sleep_1 = 1
    chain.sleep(3600 * 24 * days_to_sleep_1 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + (days_to_sleep_1 * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    print(f"")
    
    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    dump_amountA = 1_200_000 * 1e18
    print(f"Dumping some tokenA. Selling {dump_amountA / 1e18} {tokenA.symbol()}")
    router.swapExactTokensForTokens(
        dump_amountA,
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")

    hedgePayout = joint.getHedgePayout()
    print(f"Payout from Hedge: {hedgePayout/1e6} {tokenB.symbol()}")

    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")

    # Wait plz
    days_to_sleep_2 = 2
    chain.sleep(3600 * 24 * days_to_sleep_2 - 15 * 60)
    chain.mine()
    
    time_from_build = vaultA.strategies(providerA).dict()['lastReport'] + ((days_to_sleep_1 + days_to_sleep_2) * 86400)
    days_from_build = int((time_from_build - now_UNIX)/86400)
    hours_from_build = int((time_from_build - now_UNIX - (days_from_build*86400))/3600)
    print(f"")
    print(f"Time from build {days_from_build}d, {hours_from_build}h")
    
    # update oracle's price according to sushiswap
    sync_price(joint)
    pt = band_oracle.getReferenceData('FTM', 'USDC')[0]/1e18
    print(
        f"Price according to Pair is {pt}"
    )    
    
    print(f"Status in joint A {joint.estimatedTotalAssetsInToken(tokenA)/1e18} {tokenA.symbol()}")
    print(f"Status in Joint B {joint.estimatedTotalAssetsInToken(tokenB)/1e6} {tokenB.symbol()}")
    print(f"Pending reward {joint.pendingReward()/1e18:,.4f}")
    
    q = hedgil.hedgils(joint.activeHedgeID())[2]
    
    calc_il = (pt + p0 - 2 * p0 * math.sqrt(pt/p0)) * q / 1e18
    print(f"IL calculation: {calc_il:,.4f}")
    
    cost = print_hedge_status(joint, hedgil)
    investedB -= cost
    print(f"")

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    hedgeId = joint.activeHedgeID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
        
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
        
    hedgilInfo = hedgil.hedgils(hedgeId)

    assert ((hedgePayout == 0) & (hedgilInfo[5] != 0)) | (
        (hedgePayout > 0) & (hedgilInfo[5] == 0)
    )

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0

    providerA.setTakeProfit(True, {"from": strategist})
    providerB.setTakeProfit(True, {"from": strategist})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    
    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA >= 0
    assert gainB >= 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )
    
    print(f"")
    print(f"Provider A final: {vaultA.strategies(providerA).dict()}")
    print(f"")
    print(f"Provider B final: {vaultB.strategies(providerB).dict()}")


    # assert pytest.approx(returnA, rel=50e-3) == returnB


