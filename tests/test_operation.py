import brownie
import pytest
from brownie import Contract, Wei
from operator import xor
from utils import sync_price, print_hedge_status


def test_operation(
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
    strategist,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
):
    sync_price(joint, mock_chainlink, strategist)

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    ppsA_start = vaultA.pricePerShare()
    ppsB_start = vaultB.pricePerShare()

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    print_hedge_status(joint, tokenA, tokenB)
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24 - 30)
    chain.mine(int(3600 / 13) * 24)

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

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

    # Harvest should be a no-op
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})
    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    # losses due to not being able to earn enough to cover hedge without trades!
    assert vaultA.strategies(providerA).dict()["totalLoss"] > 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] > 0


def test_operation_swap_a4b(
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
):
    sync_price(joint, mock_chainlink, strategist)
    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )
    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    router.swapExactTokensForTokens(
        tokenA.balanceOf(tokenA_whale),
        0,
        [tokenA, tokenB],
        tokenA_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24 - 30)
    chain.mine(int(3600 * 24 / 13) - 30)

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

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

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA > 0
    assert lossB > 0

    returnA = -lossA / investedA
    returnB = -lossB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    assert pytest.approx(returnA, rel=50e-3) == returnB


def test_operation_swap_b4a(
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
):
    sync_price(joint, mock_chainlink, strategist)

    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
    assert joint.balanceOfStake() > 0

    investedA = (
        vaultA.strategies(providerA).dict()["totalDebt"] - providerA.balanceOfWant()
    )
    investedB = (
        vaultB.strategies(providerB).dict()["totalDebt"] - providerB.balanceOfWant()
    )
    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

    tokenB.approve(router, 2 ** 256 - 1, {"from": tokenB_whale})
    router.swapExactTokensForTokens(
        tokenB.balanceOf(tokenB_whale),
        0,
        [tokenB, tokenA],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenB_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 24)
    chain.mine(int(3600 * 24 / 13) - 30)

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e18} {tokenB.symbol()}"
    )

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

    lossA = vaultA.strategies(providerA).dict()["totalLoss"]
    lossB = vaultB.strategies(providerB).dict()["totalLoss"]

    assert lossA > 0
    assert lossB > 0

    returnA = -lossA / investedA
    returnB = -lossB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    assert pytest.approx(returnA, rel=50e-3) == returnB
