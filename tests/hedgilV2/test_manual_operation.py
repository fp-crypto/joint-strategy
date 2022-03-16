from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain

def test_return_loose_to_providers_manually(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    gov,
    hedgilV2,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
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

    # All balance should be invested
    assert tokenA.balanceOf(joint) == 0
    assert tokenB.balanceOf(joint) == 0
    assert rewards.balanceOf(joint) == 0

    # Claim rewards manually
    joint.claimRewardManually()
    assert rewards.balanceOf(joint) > 0

    # Withdraw Staked LP tokens
    joint.withdrawLPManually(joint.balanceOfStake())
    # Remove liquidity manually
    joint.removeLiquidityManually(lp_token.balanceOf(joint), 0, 0)

    # All balance should be in joint
    assert lp_token.balanceOf(joint) == 0
    assert joint.balanceOfStake() == 0
    assert tokenA.balanceOf(joint) > 0
    assert tokenB.balanceOf(joint) > 0

    # Send back to providers
    joint.returnLooseToProvidersManually()
    assert tokenA.balanceOf(joint) == 0
    assert tokenB.balanceOf(joint) == 0

    # All tokens accounted for
    assert pytest.approx(tokenA.balanceOf(providerA), rel=1e-3) == amountA
    assert pytest.approx(tokenB.balanceOf(providerB)+hedgil_position["cost"], rel=1e-3) == amountB

    # Close hedge manually
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)
    assert hedgil_position["expiration"] > 0
    joint.closeHedgeManually()
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)
    assert hedgil_position["expiration"] == 0


def test_liquidate_position_manually(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    gov,
    hedgilV2,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
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

    # CLose position manually
    joint.liquidatePositionManually(0, 0)
    # Hedgil position
    hedgil_position = hedgilV2.getHedgilByID(hedgil_id)
    assert hedgil_position["expiration"] == 0

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    # Only loss is in B token, equal to cost of hedgil position
    assert pytest.approx(vaultB.strategies(providerB)["totalLoss"], rel=1e-3) == hedgil_position["cost"]
    
def test_swap_tokens_manually(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    gov,
    hedgilV2,
    chainlink_owner,
    deployer,
    tokenA_oracle,
    tokenB_oracle,
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

    # Get rewards to swap
    joint.claimRewardManually()
    balance_rewards = rewards.balanceOf(joint)
    assert balance_rewards > 0

    # Swap half to WFTM
    joint_pre_tokenB = tokenB.balanceOf(joint)
    path = [rewards, tokenB]
    joint.swapTokenForTokenManually(path, balance_rewards / 2, 0)
    balance_rewards_post = rewards.balanceOf(joint)
    assert tokenB.balanceOf(joint) > joint_pre_tokenB
    assert pytest.approx(balance_rewards_post, rel=1e-5) == balance_rewards / 2

    # Swap remaining half to tokenA
    joint_pre_tokenA = tokenA.balanceOf(joint)
    path = [rewards, tokenB, tokenA]
    joint.swapTokenForTokenManually(path, balance_rewards_post, 0)
    assert tokenA.balanceOf(joint) > joint_pre_tokenA
    assert rewards.balanceOf(joint) == 0


