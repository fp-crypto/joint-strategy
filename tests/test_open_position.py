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
    (bal0, bal1) = joint.balanceOfTokensInLP()
    # Get lp_token
    lp_token = Contract(joint.pair())
    
    # Ensure balances are comparable
    if(lp_token.token0() == tokenA):
        balA = bal0
        balB = bal1
    else:
        balA = bal1
        balB = bal0

    # Check that total tokens still are accounted for:
    # TokenA (other token) are either in lp pool or provider A
    assert pytest.approx(balA + tokenA.balanceOf(providerA), rel=1e-5) == amountA
    # TokenB (quote token) are either in lp pool, provider B or paid to hedgil
    assert pytest.approx(balB + tokenB.balanceOf(providerB) + hedgil_position["cost"], rel=1e-5) == amountB

    # Check ratios
    (reserve0, reserve1, _) = lp_token.getReserves()
    # Check ratios between position and reserves are constant
    assert pytest.approx(bal0 / reserve0, rel=1e-5) == bal1 / reserve1

    # Check that q for hedgil is the deposited amount of other token
    assert balA == hedgil_position["initialQ"]
    # Check that strike is current price
    assert hedgil_position["strike"] == hedgilV2.getCurrentPrice(tokenA)

def test_open_position_price_change(
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

    utils.print_joint_status(joint, tokenA, tokenB, lp_token)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    # Let's move prices, 2% of tokenA reserves
    tokenA_dump = lp_token.getReserves()[0] / 50 if lp_token.token0() == tokenA else lp_token.getReserves()[1] / 50
    print(f"Dumping some {tokenA.symbol()}. Selling {tokenA_dump / (10 ** tokenA.decimals())} {tokenA.symbol()}")
    actions.dump_token(tokenA_whale, tokenA, tokenB, router, tokenA_dump)
    actions.sync_price(tokenB, lp_token, chainlink_owner, deployer, tokenB_oracle)

    utils.print_joint_status(joint, tokenA, tokenB, lp_token)
    utils.print_hedgil_status(joint, hedgilV2, tokenA, tokenB)

    (current_amount_A, current_amount_B) = joint.balanceOfTokensInLP()

    # As we have dumped some A tokens, there should be more liquidity and hence our position should have
    # more tokenA than initial and less tokenB than initial
    assert current_amount_A > initial_amount_A
    assert current_amount_B < initial_amount_B

    tokenA_excess = current_amount_A - initial_amount_A
    tokenA_excess_to_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_excess)
    
    # TokenB checksum: initial amount = current amount + tokenA excess in token B + hedgil payout 
    assert pytest.approx(current_amount_B + tokenA_excess_to_tokenB + hedgilV2.getCurrentPayout(hedgil_id), rel=1e-5) == initial_amount_B
    
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    tokenA_loss = vaultA.strategies(providerA)["totalLoss"]
    tokenB_loss = vaultB.strategies(providerB)["totalLoss"]

    tokenA_loss_in_tokenB = utils.swap_tokens_value(router, tokenA, tokenB, tokenA_loss)

    assert pytest.approx(tokenB_loss + tokenA_loss_in_tokenB, rel=1e-5) == hedgil_position["cost"]

    assert 0