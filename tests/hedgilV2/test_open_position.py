from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain

# tests harvesting a strategy that returns profits correctly
def test_setup_positions(
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
    hedge_type
):
    checks.check_run_test("hedgilV2", hedge_type)
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

    # Total assets should be equal to total amounts
    # Should this hold? Is hedgil cost accounted?
    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-2) == amountB

    # No lp tokens should remain in the joint
    assert joint.balanceOfPair() == 0
    # As they should be staked
    assert joint.balanceOfStake() > 0

    # Get the hedgil open position
    hedgil_id = joint.activeHedgeID()
    # Active position
    assert hedgil_id > 0
    # Get position details
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)

    # Get invested balances
    (balA, balB) = joint.balanceOfTokensInLP()
    # Get lp_token
    lp_token = Contract(joint.pair())

    # Check that total tokens still are accounted for:
    # TokenA (other token) are either in lp pool or provider A
    assert pytest.approx(balA + tokenA.balanceOf(providerA), rel=1e-5) == amountA
    # TokenB (quote token) are either in lp pool, provider B or paid to hedgil
    assert (
        pytest.approx(
            balB + tokenB.balanceOf(providerB) + hedgil_position["cost"], rel=1e-5
        )
        == amountB
    )

    # Check ratios
    (reserveA, reserveB) = joint.getReserves()
    # Check ratios between position and reserves are constant
    assert pytest.approx(balA / reserveA, rel=1e-5) == balB / reserveB

    # Check that q for hedgil is the deposited amount of other token
    assert pytest.approx(balA, rel=1e-5) == hedgil_position["initialQ"]
    # Check that strike is current price
    assert hedgil_position["strike"] == hedgilV2.getCurrentPrice(tokenA)


def test_open_position_price_change_tokenA(
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

    # TokenB checksum: initial amount = current amount + tokenA excess in token B + hedgil payout
    total_B_value_now = (
        current_amount_B
        + tokenA_excess_to_tokenB
        + hedgilV2.getCurrentPayout(hedgil_id)
    )
    assert pytest.approx(total_B_value_now, rel=1e-3) == initial_amount_B
    # Ensure that initial amounts are still intact taking all current data into account
    # A tokens are either in the provider strat or excess
    assert (
        pytest.approx(
            tokenA.balanceOf(providerA) + current_amount_A - tokenA_excess, rel=1e-3
        )
        == amountA
    )
    # B tokens are either in provider strat, received from A excess, used to pay hedgil cost and received as hedgil payout
    assert (
        pytest.approx(
            tokenB.balanceOf(providerB) + total_B_value_now + hedgil_position["cost"],
            rel=1e-3,
        )
        == amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    tokenA_loss_in_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_loss)

    # total loss in this case should be equal to cost of hedgil, low precision due to exchanging fees + slippage
    assert (
        pytest.approx(tokenB_loss + tokenA_loss_in_tokenB, rel=5e-2)
        == hedgil_position["cost"]
    )


def test_open_position_price_change_tokenB(
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

    # Let's move prices, 2% of tokenA reserves
    tokenB_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenB
        else lp_token.getReserves()[1] / 50
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

    # TokenA checksum: initial amount = current amount + tokenB excess in token A
    total_A_value_now = current_amount_A + tokenB_excess_to_tokenA

    assert pytest.approx(total_A_value_now, rel=1e-3) == initial_amount_A
    # Ensure that initial amounts are still intact taking all current data into account
    # A tokens are either in the provider strat or excess
    assert (
        pytest.approx(tokenA.balanceOf(providerA) + total_A_value_now, rel=1e-3)
        == amountA
    )
    # B tokens are either in provider strat, received from A excess, used to pay hedgil cost and received as hedgil payout
    assert (
        pytest.approx(
            tokenB.balanceOf(providerB)
            + current_amount_B
            - tokenB_excess
            + hedgil_position["cost"],
            rel=1e-3,
        )
        == amountB
    )

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)
    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    tokenA_loss_in_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_loss)

    # total loss in this case should be equal to cost of hedgil, low precision due to exchanging fees + slippage
    assert (
        pytest.approx(tokenB_loss + tokenA_loss_in_tokenB, rel=5e-2)
        == hedgil_position["cost"]
    )


def test_open_position_price_change_tokenA_rewards(
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
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle, tokenA_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there should be more liquidity and hence our position should have
    # more tokenA than initial and less tokenB than initial
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    actions.airdrop_rewards(rewards_whale, 2000e18, router, rewards, joint, tokenB)
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


def test_open_position_price_change_tokenB_rewards(
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

    # Let's move prices, 2% of tokenA reserves
    tokenB_dump = (
        lp_token.getReserves()[0] / 50
        if lp_token.token0() == tokenB
        else lp_token.getReserves()[1] / 50
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

    actions.airdrop_rewards(rewards_whale, 2000e18, router, rewards, joint, tokenB)
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
