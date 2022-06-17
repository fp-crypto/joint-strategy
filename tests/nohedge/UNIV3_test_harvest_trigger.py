import eth_utils
import pytest
from brownie import Contract, chain, interface, history
from eth_abi.packed import encode_abi_packed
from utils import actions, checks, utils

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["crv"])
def test_recenter_joint_UNIV3(
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
    swap_from,
    swap_dex,
    uniswap_helper_views,
    testing_library,
    univ3_pool_fee
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
    chain.mine(1)

    n_ticks = 3

    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB, True)
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    if uni_v3_pool.token0() == tokenA.address:
        next_tick = current_tick - n_ticks if swap_from == "a" else current_tick + n_ticks
    else:
        next_tick = current_tick + n_ticks if swap_from == "a" else current_tick - n_ticks
    
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1
    
    sell_amount = 1000e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)

    joint.setMinRewardToHarvest(1e18, {"from": gov})
    
    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    providerA.harvest()
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == True
    providerB.harvest()
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False

    assert providerA.launchHarvest() == False
    assert providerB.launchHarvest() == False

    providerA.setLaunchHarvest(True, {"from": gov})
    providerB.setLaunchHarvest(True, {"from": gov})
    
    assert providerA.launchHarvest() == True
    assert providerB.launchHarvest() == True

    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    providerA.harvest()
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == True
    providerB.harvest()
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["crv"])
def test_compound_fees_joint_UNIV3(
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
    swap_from,
    swap_dex,
    uniswap_helper_views,
    testing_library,
    univ3_pool_fee
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
    chain.mine(1)

    n_ticks = 1

    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.harvestTrigger(1) == False
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.harvestTrigger(1) == False

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    if uni_v3_pool.token0() == tokenA.address:
        next_tick = current_tick - n_ticks if swap_from == "a" else current_tick + n_ticks
    else:
        next_tick = current_tick + n_ticks if swap_from == "a" else current_tick - n_ticks
    
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1
    
    sell_amount = 1000e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)
    joint.setMinRewardToHarvest(1e18, {"from": gov})
    assert joint.harvestTrigger(1) == False
    joint.setMinRewardToHarvest(0, {"from": gov})
    swap_from = "b" if swap_from =="a" else "a"
    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    if uni_v3_pool.token0() == tokenA.address:
        next_tick = current_tick - n_ticks if swap_from == "a" else current_tick + n_ticks
    else:
        next_tick = current_tick + n_ticks if swap_from == "a" else current_tick - n_ticks
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1
    sell_amount = 1000e6 * 10 ** token_in.decimals()
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)

    assert joint.harvestTrigger(1) == False
    (pendingA, pendingB) = joint.pendingRewards()
    (beforeA, beforeB) = joint.balanceOfTokensInLP()
    joint.setMinRewardToHarvest(1e18, {"from": gov})
    assert joint.harvestTrigger(1) == True
    joint.harvest()
    assert joint.pendingRewards() == (0, 0)
    (afterA, afterB) = joint.balanceOfTokensInLP()
    assert ((afterA - beforeA) == pendingA) or ((afterB - beforeB) == pendingB)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)