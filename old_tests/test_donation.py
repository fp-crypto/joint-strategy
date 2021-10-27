import brownie
import pytest
from utils import sync_price


def test_donation_provider(
    chain,
    vaultA,
    tokenA,
    providerA,
    joint,
    strategist,
    tokenA_whale,
    mock_chainlink,
):
    sync_price(joint, mock_chainlink, strategist)
    ppsA_start = vaultA.pricePerShare()

    amount = 1e18
    tokenA.transfer(providerA, amount, {"from": tokenA_whale})
    assert providerA.balanceOfWant() == amount

    providerA.harvest({"from": strategist})
    assert joint.estimatedTotalAssetsInToken(tokenA) == 0

    chain.sleep(60 * 60 * 8)
    chain.mine(1)
    assert vaultA.strategies(providerA).dict()["totalGain"] == amount

    assert vaultA.pricePerShare() > ppsA_start


def test_donation_joint(
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
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    tokenA.approve(router, 2 ** 256 - 1, {"from": tokenA_whale})
    router.swapExactTokensForTokens(
        tokenA.balanceOf(tokenA_whale),
        0,
        [tokenA, tokenB],
        tokenB_whale,
        2 ** 256 - 1,
        {"from": tokenA_whale},
    )

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # Wait plz
    chain.sleep(3600 * 1)
    chain.mine(int(3600 / 13))

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # If there is any profit it should go to the providers
    assert joint.pendingReward() > 0

    amount = tokenB.balanceOf(tokenB_whale)
    tokenB.transfer(joint, amount, {"from": tokenB_whale})
    assert joint.balanceOfB() == amount

    print(
        f"Joint estimated assets: {joint.estimatedTotalAssetsInToken(tokenA) / 1e18} {tokenA.symbol()} and {joint.estimatedTotalAssetsInToken(tokenB) / 1e6} {tokenB.symbol()}"
    )

    # If joint doesn't reinvest, and providers do not invest want, the want
    # will stay in the providers
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})
    providerA.harvest({"from": strategist})
    providerB.harvest({"from": strategist})

    assert tokenA.balanceOf(vaultA) > 0
    assert tokenB.balanceOf(vaultB) > 0

    assert vaultA.strategies(providerA).dict()["totalLoss"] == 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] == 0

    gainA = vaultA.strategies(providerA).dict()["totalGain"]
    gainB = vaultB.strategies(providerB).dict()["totalGain"]

    assert gainA > 0
    assert gainB > 0

    returnA = gainA / investedA
    returnB = gainB / investedB

    print(
        f"Return: {returnA*100:.5f}% {tokenA.symbol()} {returnB*100:.5f}% {tokenB.symbol()}"
    )

    chain.sleep(60 * 60 * 8)
    chain.mine(1)

    assert vaultA.pricePerShare() > ppsA_start
    assert vaultB.pricePerShare() > ppsB_start
