from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, reverts


def test_lp_token_airdrop_joint_open(
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
    hedgilV2,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    dai,
    rewards,
    rewards_whale,
    lp_whale,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 2% of tokenA reserves
    tokenA_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenA
        else lp_token.getReserves()[1] / 50
    )
    print(
        f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}"
    )
    actions.dump_token(tokenA_whale, tokenA, tokenB, router, tokenA_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Dump some lp_tokens into the strat while positions are open
    lp_token.transfer(joint, lp_token.balanceOf(lp_whale) / 2, {"from": lp_whale})

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some lp tokens, both balances should be higher than initial values
    assert current_amount_A > initial_amount_A
    assert current_amount_B > initial_amount_B

    # As there is quite a bit of profit, remove healthchecks
    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss == 0
    assert tokenB_loss == 0

    vaultA.strategies(providerA)["totalDebt"] == 0
    vaultB.strategies(providerB)["totalDebt"] == 0

    vaultA.strategies(providerA)["totalGain"] > 0
    vaultB.strategies(providerB)["totalGain"] > 0


def test_lp_token_airdrop_joint_closed(
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
    hedgilV2,
    tokenA_whale,
    tokenB_whale,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
    router,
    dai,
    rewards,
    rewards_whale,
    lp_whale,
):

    # Dump some lp_tokens into the strat while positions are closed
    lp_token = Contract(joint.pair())
    lp_token.transfer(joint, lp_token.balanceOf(lp_whale) / 2, {"from": lp_whale})
    # Make sure joint has lp balance
    assert joint.balanceOfPair() > 0

    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)

    # Start the epoch but providerB reverts as there is balanceOfPair()
    providerA.harvest({"from": gov})
    with reverts():
        providerB.harvest({"from": gov})

    # Existing liquidity in LP is removed to make sure we start clean
    joint.removeLiquidityManually(lp_token.balanceOf(joint), 0, 0, {"from": gov})

    # We can now harvest providerB
    providerB.harvest({"from": gov})
    # Set debt ratios to 0
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    assert joint.investedA() > 0
    assert joint.investedB() > 0
    assert joint.activeHedgeID() > 0

    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)

    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 2% of tokenA reserves
    tokenA_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenA
        else lp_token.getReserves()[1] / 50
    )
    print(
        f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}"
    )
    actions.dump_token(tokenA_whale, tokenA, tokenB, router, tokenA_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there is less liquidity of B
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    # As there is quite a bit of profit, remove healthchecks
    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss == 0
    assert tokenB_loss == 0

    vaultA.strategies(providerA)["totalDebt"] == 0
    vaultB.strategies(providerB)["totalDebt"] == 0

    vaultA.strategies(providerA)["totalGain"] > 0
    vaultB.strategies(providerB)["totalGain"] > 0


def test_lp_token_airdrop_joint_closed_sweep(
    joint,
    gov,
    lp_whale,
):

    # Dump some lp_tokens into the strat while positions are closed
    lp_token = Contract(joint.pair())
    lp_token.transfer(joint, lp_token.balanceOf(lp_whale), {"from": lp_whale})
    # Make sure joint has lp balance
    pre_balance = joint.balanceOfPair()
    assert pre_balance > 0

    # Sweep the strat lp_token
    joint.sweep(lp_token, {"from": gov})
    # Ensure there is no more balance in joint
    assert joint.balanceOfPair() == 0
    # Ensure that all balance has been swept
    assert lp_token.balanceOf(gov) == pre_balance
