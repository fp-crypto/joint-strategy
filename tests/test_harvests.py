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
    whitelist_borrower
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, joint, vaultA, amountA
    )

    total_assets_tokenA = providerA.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA

    utils.sleep()
    # TODO: Add some code before harvest #2 to simulate earning yield
    profit_amount_percentage = 0.01
    profit_amount_tokenA = actions.generate_profit(
        profit_amount_percentage,
        joint,
        providerA,
        tokenA_whale,
    )
    # check that estimatedTotalAssets estimates correctly
    assert (
        pytest.approx(total_assets_tokenA + profit_amount_tokenA, rel=5 * 1e-3)
        == providerA.estimatedTotalAssets()
    )

    before_pps_tokenA = vaultA.pricePerShare()
    # Harvest 2: Realize profit
    chain.sleep(1)

    actions.gov_end_epoch(gov, providerA, joint, vaultA)

    utils.sleep()  # sleep for 6 hours

    total_debt_tokenB = providerB.updatedBalanceOfDebt({'from': strategist}).return_value
    assert total_debt_tokenB == 0
    # all the balance (principal + profit) is in vault
    total_balance_tokenA = vaultA.totalAssets()

    assert (
        pytest.approx(total_balance_tokenA, rel=1e-2)
        == amountA + profit_amount_tokenA
    )
    assert vaultA.pricePerShare() > before_pps_tokenA


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

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, joint, vaultA, amountA
    )

    providerA.setDoHealthCheck(False, {"from": gov})

    # We will have a loss when closing the epoch because we have spent money on Hedging
    chain.sleep(1)
    tx = providerA.harvest({"from": strategist})
    lossA = tx.events["Harvested"]["loss"]
    assert lossA > 0

    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    # User will withdraw accepting losses
    assert tokenA.balanceOf(vaultA) + lossA == amountA
