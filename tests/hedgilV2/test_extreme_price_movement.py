from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain


def test_extreme_price_movement_tokenA(
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
    hedge_type,
):
    checks.check_run_test("hedgilV2", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 10% of tokenA reserves
    tokenA_dump = (
        lp_token.getReserves()[0] / 10
        if lp_token.token0() == tokenA
        else lp_token.getReserves()[1] / 10
    )
    print(
        f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}"
    )
    actions.dump_token(tokenA_whale, tokenA, tokenB, router, tokenA_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there should be more liquidity and hence our position should have
    # more tokenA than initial and less tokenB than initial
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    tokenA_excess = current_amount_A - initial_amount_A
    tokenA_excess_to_tokenB = utils.swap_tokens_value(
        router, tokenA, tokenB, tokenA_excess
    )

    # TokenB checksum: initial amount > current amount + tokenA excess in token B + hedgil payout as
    # hedgil does not cover the entire IL, needed to be closed before!
    total_B_value_now = (
        current_amount_B
        + tokenA_excess_to_tokenB
        + hedgilV2.getCurrentPayout(hedgil_id)
    )
    assert total_B_value_now < initial_amount_B
    # Initial amounts are not intact as there is an unhedged loss
    assert tokenA.balanceOf(providerA) + current_amount_A - tokenA_excess < amountA
    assert (
        tokenB.balanceOf(providerB) + total_B_value_now + hedgil_position["cost"]
        < amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    tokenA_loss_in_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_loss)

    # total loss in this case should be higher to cost of hedgil
    assert tokenB_loss + tokenA_loss_in_tokenB > hedgil_position["cost"]


def test_extreme_price_movement_tokenA_with_rewards(
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
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 10% of tokenA reserves
    tokenA_dump = (
        lp_token.getReserves()[0] / 10
        if lp_token.token0() == tokenA
        else lp_token.getReserves()[1] / 10
    )
    print(
        f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}"
    )
    actions.dump_token(tokenA_whale, tokenA, tokenB, router, tokenA_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there should be more liquidity and hence our position should have
    # more tokenA than initial and less tokenB than initial
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    actions.airdrop_rewards(rewards_whale, 4000e18, router, rewards, joint, tokenB)
    assert joint.balanceOfReward() > 0

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss == 0
    assert tokenB_loss == 0

    vaultA.strategies(providerA)["totalDebt"] == 0
    vaultB.strategies(providerB)["totalDebt"] == 0

    vaultA.strategies(providerA)["totalGain"] > 0
    vaultB.strategies(providerB)["totalGain"] > 0


def test_extreme_price_movement_tokenB(
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
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 10% of tokenB reserves
    tokenB_dump = (
        lp_token.getReserves()[0] / 10
        if lp_token.token0() == tokenB
        else lp_token.getReserves()[1] / 10
    )
    print(
        f"Dumping some {tokenB.symbol()}. Selling {tokenB_dump / (10 ** tokenB.decimals())} {tokenB.symbol()}"
    )
    actions.dump_token(tokenB_whale, tokenB, tokenA, router, tokenB_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some B tokens, there should be more liquidity and hence our position should have
    # more tokenB than initial and less tokenA than initial
    assert current_amount_A < initial_amount_A
    assert current_amount_B > initial_amount_B

    tokenB_excess = current_amount_B - initial_amount_B
    tokenB_excess_to_tokenA = utils.swap_tokens_value(
        router, tokenB, tokenA, tokenB_excess
    )

    # TokenA checksum: initial amount > current amount + tokenB excess in token A
    total_A_value_now = current_amount_A + tokenB_excess_to_tokenA
    assert total_A_value_now < initial_amount_A
    # Initial amounts are not intact as there is an unhedged loss
    assert tokenA.balanceOf(providerA) + total_A_value_now < amountA
    assert (
        tokenB.balanceOf(providerB)
        + current_amount_B
        - tokenB_excess
        + hedgil_position["cost"]
        < amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    tokenA_loss_in_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_loss)

    # total loss in this case should be higher to cost of hedgil
    assert tokenB_loss + tokenA_loss_in_tokenB > hedgil_position["cost"]


def test_extreme_price_movement_tokenB_with_rewards(
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
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    lp_token = Contract(joint.pair())
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 10% of tokenB reserves
    tokenB_dump = (
        lp_token.getReserves()[0] / 10
        if lp_token.token0() == tokenB
        else lp_token.getReserves()[1] / 10
    )
    print(
        f"Dumping some {tokenB.symbol()}. Selling {tokenB_dump / (10 ** tokenB.decimals())} {tokenB.symbol()}"
    )
    actions.dump_token(tokenB_whale, tokenB, tokenA, router, tokenB_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some B tokens, there should be more liquidity and hence our position should have
    # more tokenB than initial and less tokenA than initial
    assert current_amount_A < initial_amount_A
    assert current_amount_B > initial_amount_B

    actions.airdrop_rewards(rewards_whale, 4000e18, router, rewards, joint, tokenB)
    assert joint.balanceOfReward() > 0

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    assert tokenA_loss == 0
    assert tokenB_loss == 0

    vaultA.strategies(providerA)["totalDebt"] == 0
    vaultB.strategies(providerB)["totalDebt"] == 0

    vaultA.strategies(providerA)["totalGain"] > 0
    vaultB.strategies(providerB)["totalGain"] > 0
