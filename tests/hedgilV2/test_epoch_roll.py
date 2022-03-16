from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain

def test_triggers_and_roll_epoch(
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
    # As it's the first one
    assert joint.shouldStartEpoch() == False
    assert joint.shouldEndEpoch() == False
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

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

    actions.airdrop_rewards(rewards_whale, 2000e18, router, rewards, joint, tokenB)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token, rewards)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    chain.mine(1, timestamp= hedgil_position["expiration"] - 3600 + 1)
    assert joint.shouldStartEpoch() == False
    assert joint.shouldEndEpoch() == True
    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    # First provider is harvested
    providerA.harvest({"from": gov})
    assert joint.balanceOfA() > 0
    assert joint.balanceOfB() == 0
    # Position is closed
    assert joint.activeHedgeID() == 0

    # Should Start Epoch is then true
    assert joint.shouldStartEpoch() == True
    # And then rpoviderB harvest trigger also
    assert providerB.harvestTrigger(1) == True

    providerB.harvest({"from": gov})

    # New epoch started
    assert joint.activeHedgeID() > 0
    assert joint.activeHedgeID() > hedgil_id
    assert joint.balanceOfStake() > 0

    assert joint.shouldStartEpoch() == False    
    assert joint.shouldEndEpoch() == False    
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False

    hedgil_position = hedgilV2.getHedgilByID(joint.activeHedgeID())

    assert pytest.approx(hedgil_position["expiration"] - chain.time(), rel=1e-3) == 2 * 86_400