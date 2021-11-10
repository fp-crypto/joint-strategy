from utils import actions, checks, utils
import pytest
from brownie import Contract, chain

# tests harvesting a strategy that returns profits correctly
def test_profitable_harvest(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assets_tokenA = providerA.estimatedTotalAssets()
    total_assets_tokenB = providerB.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-2) == amountB

    # TODO: Add some code before harvest #2 to simulate earning yield
    profit_amount_percentage = 0.0095
    profit_amount_tokenA, profit_amount_tokenB = actions.generate_profit(
        profit_amount_percentage,
        joint,
        providerA,
        providerB,
        tokenA_whale,
        tokenB_whale,
    )

    # check that estimatedTotalAssets estimates correctly
    assert (
        pytest.approx(total_assets_tokenA + profit_amount_tokenA, rel=5 * 1e-3)
        == providerA.estimatedTotalAssets()
    )
    assert (
        pytest.approx(total_assets_tokenB + profit_amount_tokenB, rel=5 * 1e-3)
        == providerB.estimatedTotalAssets()
    )

    before_pps_tokenA = vaultA.pricePerShare()
    before_pps_tokenB = vaultB.pricePerShare()
    # Harvest 2: Realize profit
    chain.sleep(1)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    utils.sleep()  # sleep for 6 hours

    # all the balance (principal + profit) is in vault
    total_balance_tokenA = vaultA.totalAssets()
    total_balance_tokenB = vaultB.totalAssets()
    assert (
        pytest.approx(total_balance_tokenA, rel=5 * 1e-3)
        == amountA + profit_amount_tokenA
    )
    assert (
        pytest.approx(total_balance_tokenB, rel=5 * 1e-3)
        == amountB + profit_amount_tokenB
    )
    assert vaultA.pricePerShare() > before_pps_tokenA
    assert vaultB.pricePerShare() > before_pps_tokenB


# TODO: implement this
# tests harvesting a strategy that reports losses
def test_lossy_harvest(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    # We will have a loss when closing the epoch because we have spent money on Hedging
    chain.sleep(1)
    tx = providerA.harvest({"from": strategist})
    lossA = tx.events["Harvested"]["loss"]
    assert lossA > 0
    tx = providerB.harvest({"from": strategist})
    lossB = tx.events["Harvested"]["loss"]
    assert lossB > 0
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    # User will withdraw accepting losses
    assert tokenA.balanceOf(vaultA) + lossA == amountA
    assert tokenB.balanceOf(vaultB) + lossB == amountB
