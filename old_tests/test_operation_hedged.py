import brownie
import pytest
from brownie import Contract, Wei, chain
from operator import xor
from utils import print_hedge_status, sync_price


def test_operation_swap_a4b_hedged_light(
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
    strategist,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    LPHedgingLibrary,
    oracle,
):
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

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

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    print_hedge_status(joint, tokenA, tokenB)

    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    dump_amountA = 3_000 * 1e18
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
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    (callPayout, putPayout) = joint.getHedgeProfit()
    print(f"Payout from CALL option: {callPayout/1e18} {tokenA.symbol()}")
    print(f"Payout from PUT option: {putPayout/1e6} {tokenB.symbol()}")

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24 * 1 - 15 * 60)
    chain.mine(int(3600 / 13) * 24 * 1 - int(60 * 15 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)

    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    callID = joint.activeCallID()
    putID = joint.activePutID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": vaultA.governance()})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": vaultB.governance()})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    callInfo = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d").options(callID)
    putInfo = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b").options(putID)

    assert ((callInfo[0] == 2) & (callPayout > 0)) | (
        (callPayout == 0) & (callInfo[0] == 1)
    )
    assert ((putInfo[0] == 2) & (putPayout > 0)) | (
        (putPayout == 0) & (putInfo[0] == 1)
    )

    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA == 0
    assert lossB == 0
    assert gainA > 0
    assert gainB > 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    # assert pytest.approx(returnA, rel=50e-3) == returnB


def test_operation_swap_a4b_hedged_heavy(
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
    strategist,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    LPHedgingLibrary,
    oracle,
):

    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

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

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    print_hedge_status(joint, tokenA, tokenB)

    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    print(
        f"Dumping tokenA really bad. Selling {tokenA.balanceOf(tokenA_whale) / 1e18} {tokenA.symbol()}"
    )
    router.swapExactTokensForTokens(
        tokenA.balanceOf(tokenA_whale),
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )

    # update oracle's price according to sushiswap
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    (callPayout, putPayout) = joint.getHedgeProfit()
    print(f"Payout from CALL option: {callPayout/1e18} {tokenA.symbol()}")
    print(f"Payout from PUT option: {putPayout/1e6} {tokenB.symbol()}")

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24 * 1 - 15 * 60)
    chain.mine(int(3600 / 13) * 24 * 1 - int(60 * 15 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)
    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    callID = joint.activeCallID()
    putID = joint.activePutID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": vaultA.governance()})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": vaultB.governance()})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    callInfo = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d").options(callID)
    putInfo = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b").options(putID)

    assert ((callInfo[0] == 2) & (callPayout > 0)) | (
        (callPayout == 0) & (callInfo[0] == 1)
    )
    assert ((putInfo[0] == 2) & (putPayout > 0)) | (
        (putPayout == 0) & (putInfo[0] == 1)
    )

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA > 0
    assert lossB > 0

    # we are not hedging against this heavy moves (99%)
    returnA = -lossA / investedA
    returnB = -lossB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    # assert pytest.approx(returnA, rel=50e-3) == returnB


def test_operation_swap_b4a_hedged_light(
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
    strategist,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    LPHedgingLibrary,
    oracle,
):
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
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

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    print_hedge_status(joint, tokenA, tokenB)

    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    dump_amountB = 7_000_000 * 1e6
    print(f"Dumping some tokenB. Selling {dump_amountB / 1e6} {tokenB.symbol()}")

    router.swapExactTokensForTokens(
        dump_amountB,
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )

    # update oracle's price according to sushiswap
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    (callPayout, putPayout) = joint.getHedgeProfit()
    print(f"Payout from CALL option: {callPayout/1e18} {tokenA.symbol()}")
    print(f"Payout from PUT option: {putPayout/1e6} {tokenB.symbol()}")

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24 * 1 - 15 * 60)
    chain.mine(int(3600 / 13) * 24 * 1 - int(60 * 15 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )
    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)
    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    callID = joint.activeCallID()
    putID = joint.activePutID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": vaultA.governance()})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": vaultB.governance()})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    callInfo = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d").options(callID)
    putInfo = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b").options(putID)

    assert ((callInfo[0] == 2) & (callPayout > 0)) | (
        (callPayout == 0) & (callInfo[0] == 1)
    )
    assert ((putInfo[0] == 2) & (putPayout > 0)) | (
        (putPayout == 0) & (putInfo[0] == 1)
    )

    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    assert gainA > 0
    assert gainB > 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    # assert pytest.approx(returnA, rel=50e-3) == returnB


def test_operation_swap_b4a_hedged_heavy(
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
    strategist,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    LPHedgingLibrary,
    oracle,
):

    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
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

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    print_hedge_status(joint, tokenA, tokenB)

    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    print(
        f"Dumping tokenB really bad. Selling {tokenB.balanceOf(tokenB_whale) / 1e6} {tokenB.symbol()}"
    )

    router.swapExactTokensForTokens(
        tokenB.balanceOf(tokenB_whale),
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )
    # update oracle's price according to sushiswap
    sync_price(joint, mock_chainlink, strategist)
    print(f"Price according to Pair is {oracle.latestAnswer()/1e8}")

    (callPayout, putPayout) = joint.getHedgeProfit()
    print(f"Payout from CALL option: {callPayout/1e18} {tokenA.symbol()}")
    print(f"Payout from PUT option: {putPayout/1e6} {tokenB.symbol()}")

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )
    currentA = joint.estimatedTotalAssetsInToken(tokenA)
    currentB = joint.estimatedTotalAssetsInToken(tokenB)
    assert currentA / currentB == pytest.approx(startingA / startingB, rel=50e-3)
    print(
        f"Current RatioA/B: {currentA/currentB} vs initial ratio A/B {startingA/startingB}"
    )

    callID = joint.activeCallID()
    putID = joint.activePutID()

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0
    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": vaultA.governance()})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": vaultB.governance()})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    callInfo = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d").options(callID)
    putInfo = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b").options(putID)

    assert ((callInfo[0] == 2) & (callPayout > 0)) | (
        (callPayout == 0) & (callInfo[0] == 1)
    )
    assert ((putInfo[0] == 2) & (putPayout > 0)) | (
        (putPayout == 0) & (putInfo[0] == 1)
    )

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA > 0
    assert lossB > 0

    returnA = -lossA / investedA
    returnB = -lossB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    # assert pytest.approx(returnA, rel=50e-3) == returnB
