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

    actions.gov_start_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    total_assets_tokenA = providerA.estimatedTotalAssets()
    total_assets_tokenB = providerB.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-2) == amountB

    # TODO: Add some code before harvest #2 to simulate earning yield
    profit_amount_percentage = 0.02
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

    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

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
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    actions.user_deposit(user, vault, token, amount)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    total_assets = strategy.estimatedTotalAssets()
    assert pytest.approx(total_assets, rel=RELATIVE_APPROX) == amount

    # TODO: Add some code before harvest #2 to simulate a lower pps
    loss_amount = amount * 0.05
    actions.generate_loss(loss_amount)

    # check that estimatedTotalAssets estimates correctly
    assert total_assets - loss_amount == strategy.estimatedTotalAssets()

    # Harvest 2: Realize loss
    chain.sleep(1)
    tx = strategy.harvest({"from": strategist})
    checks.check_harvest_loss(tx, loss_amount)
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    # User will withdraw accepting losses
    vault.withdraw(vault.balanceOf(user), user, 10_000, {"from": user})
    assert token.balanceOf(user) + loss_amount == amount


# TODO: implement this
# tests harvesting a strategy twice, once with loss and another with profit
# it checks that even with previous profit and losses, accounting works as expected
def test_choppy_harvest(
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    actions.user_deposit(user, vault, token, amount)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest({"from": strategist})

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # TODO: Add some code before harvest #2 to simulate a lower pps
    loss_amount = amount * 0.05
    actions.generate_loss(loss_amount)

    # Harvest 2: Realize loss
    chain.sleep(1)
    tx = strategy.harvest({"from": strategist})
    checks.check_harvest_loss(tx, loss_amount)

    # TODO: Add some code before harvest #3 to simulate a higher pps ()
    profit_amount = amount * 0.1  # 10% profit
    actions.generate_profit(profit_amount)

    chain.sleep(1)
    tx = strategy.harvest({"from": strategist})
    checks.check_harvest_profit(tx, profit_amount)

    # User will withdraw accepting losses
    vault.withdraw({"from": user})

    # User will take 100% losses and 100% profits
    assert token.balanceOf(user) == amount + profit_amount - loss_amount
