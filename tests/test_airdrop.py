from utils import actions, checks, utils
import pytest


def test_airdrop(
    chain,
    accounts,
    token,
    vault,
    strategy,
    user,
    strategist,
    amount,
    RELATIVE_APPROX,
    token_whale,
):
    # Deposit to the vault
    actions.user_deposit(user, vault, token, amount)

    # Harvest 1: Send funds through the strategy
    # start epoch

    total_assets = strategy.estimatedTotalAssets()
    assert pytest.approx(total_assets, rel=RELATIVE_APPROX) == amount

    # we airdrop tokens to strategy
    # TODO: airdrop LP token to joint
    airdrop_amount = amount * 0.1  # 10% of current assets
    token.transfer(strategy, airdrop_amount, {"from": token_whale})

    # TODO: airdrop tokenA to joint

    # TODO: airdrop tokenB to joint

    # check that estimatedTotalAssets estimates correctly
    assert total_assets + airdrop_amount == strategy.estimatedTotalAssets()

    before_pps = vault.pricePerShare()
    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault
    # TODO: Uncomment the lines below
    assert token.balanceOf(strategy) + profit > amount
    assert vault.pricePerShare() > before_pps


def test_airdrop_providers(
    chain,
    accounts,
    token,
    vault,
    strategy,
    user,
    strategist,
    amount,
    RELATIVE_APPROX,
    token_whale,
):
    # set debtRatio of providerA to 0

    # airdrop token

    # harvest and check it has been taken as profit
    token_whale


def test_airdrop_providers(
    chain,
    accounts,
    token,
    vault,
    strategy,
    user,
    strategist,
    amount,
    RELATIVE_APPROX,
    token_whale,
):
    # start epoch

    # airdrop token to providerA

    # finish epoch

    # check that it has been taken as profit for providerA only
    token_whale
