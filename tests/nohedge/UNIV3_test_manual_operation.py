from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, reverts

@pytest.mark.parametrize("swap_from", ["a", "b"])
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
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    hedge_type,
    dex,
    uni_v3_pool,
    router,
    uniswap_helper_views,
    testing_library,
    univ3_pool_fee,
    joint_to_use,
    weth,
    swap_from
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Try to inject a false address as pool
    with reverts():
        joint.setUniPool("0x3416cf6c708da44db2624d63ea0aaef7113527c5", 100)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # All balance should be invested
    assert tokenA.balanceOf(joint) == 0
    assert tokenB.balanceOf(joint) == 0
    assert joint.pendingRewards() == (0,0)

    # Trade a small amount to generate rewards
    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    token_out_whale = tokenB_whale if swap_from == "a" else tokenA_whale

    sell_amount = 1_000 * (10**token_in.decimals())
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee)

    # We have generated rewards
    pending_rewards = joint.pendingRewards()
    assert pending_rewards != (0, 0)

    reward_gains = pending_rewards[0] if pending_rewards[0] > 0 else pending_rewards[1]
    # Claim rewards manually
    balA, balB = joint.pendingRewards()
    with reverts():
        tx = joint.burnLPManually(0, joint.minTick(), joint.maxTick(), balA*1.1, balB*1.1, {"from": gov})
    tx = joint.burnLPManually(0, joint.minTick(), joint.maxTick(), balA*0.99, balB*0.99, {"from": gov})
    if reward_gains == pending_rewards[0]:
        assert tx.events["Collect"]["amount0"] == reward_gains
    else:
        assert tx.events["Collect"]["amount1"] == reward_gains
    # Remove liquidity manually
    tx = joint.removeLiquidityManually(joint.balanceOfPool(), 0, 0, {"from": gov})

    # All balance should be in joint
    assert tokenA.balanceOf(joint) > 0
    assert tokenB.balanceOf(joint) > 0

    # Send back to providers
    joint.returnLooseToProvidersManually()
    assert tokenA.balanceOf(joint) == 0
    assert tokenB.balanceOf(joint) == 0

    # All tokens accounted for
    assert pytest.approx(tokenA.balanceOf(providerA), rel=1e-3) == amountA
    assert pytest.approx(tokenB.balanceOf(providerB), rel=1e-3) == amountB

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
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    hedge_type,
    dex,
    uni_v3_pool,
    router,
    uniswap_helper_views,
    testing_library,
    univ3_pool_fee,
    joint_to_use,
    weth,
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    (initial_amount_A, initial_amount_B) = joint.balanceOfTokensInLP()

    # CLose position manually
    joint.liquidatePositionManually(0, 0)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert joint.investedA() == 0
    assert joint.investedB() == 0

    for (vault, strat) in zip([vaultA, vaultB], [providerA, providerB]):
        assert vault.strategies(strat)["totalLoss"] >= 0
        assert vault.strategies(strat)["totalGain"] == 0
        assert vault.strategies(strat)["totalDebt"] == 0
    
@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["uni", "crv"])
def test_manual_swaps(
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
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    hedge_type,
    dex,
    uni_v3_pool,
    router,
    uniswap_helper_views,
    testing_library,
    univ3_pool_fee,
    joint_to_use,
    weth,
    swap_from,
    swap_dex
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)

    if swap_dex == "uni":
        joint.setUseCRVPool(False, {"from": gov})
    else:
        joint.setUseCRVPool(True, {"from": gov})

    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    # Trade a small amount to generate rewards
    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    sell_amount = 1_000 * (10**token_in.decimals())
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee)

    tx = joint.removeLiquidityManually(joint.balanceOfPool(), 0, 0, {"from": gov})

    if swap_from == "a":
        sell_A = True
        amount = joint.balanceOfA() - joint.investedA()
    else:
        sell_A = False
        amount = joint.balanceOfB() - joint.investedB()
    
    joint.swapTokenForTokenManually(
        sell_A,
        amount,
        0,
        {"from": gov}
    )

    # All balance should be in joint
    assert pytest.approx(joint.balanceOfA(), rel=RELATIVE_APPROX) == joint.investedA()
    assert pytest.approx(joint.balanceOfB(), rel=RELATIVE_APPROX) == joint.investedB()

    # Send back to providers
    joint.returnLooseToProvidersManually()

    assert joint.investedA() > 0
    assert joint.investedB() > 0

    # All tokens accounted for
    assert pytest.approx(tokenA.balanceOf(providerA), rel=1e-3) == amountA
    assert pytest.approx(tokenB.balanceOf(providerB), rel=1e-3) == amountB

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert joint.investedA() == 0
    assert joint.investedB() == 0
