from xxlimited import new
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, interface
import eth_utils
from eth_abi.packed import encode_abi_packed

@pytest.mark.parametrize("swap_from", ["a", "b"])
def test_one_tick_UNIV3(
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
    simulate_swap
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    n_ticks = 1

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    next_tick = current_tick - 1 if swap_from == "a" else current_tick + 1
    # limit_price = simulate_swap.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else simulate_swap.getSqrtRatioAtTick(next_tick) - 1
    limit_price = simulate_swap.getSqrtRatioAtTick(next_tick) + 1

    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)
    
    sell_amount = 100e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, limit_price)

    new_tick = uni_v3_pool.slot0()["tick"]
    assert abs(new_tick - current_tick) == n_ticks

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

@pytest.mark.parametrize("swap_from", ["a", "b"])
def test_multiple_ticks_UNIV3(
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
    simulate_swap
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    n_ticks = 3

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    next_tick = current_tick - n_ticks if swap_from == "a" else current_tick + n_ticks
    # limit_price = simulate_swap.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else simulate_swap.getSqrtRatioAtTick(next_tick) - 1
    limit_price = simulate_swap.getSqrtRatioAtTick(next_tick) + 1

    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)
    
    sell_amount = 100e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, limit_price)

    new_tick = uni_v3_pool.slot0()["tick"]
    assert abs(new_tick - current_tick) == n_ticks

    rewards_pending = joint.pendingRewards()
    
    if joint.maxTick() < new_tick or new_tick < joint.minTick():
        if swap_from == "a":
            assert joint.balanceOfTokensInLP()[1] == 0
        else:
            assert joint.balanceOfTokensInLP()[0] == 0
        sell_amount = 100 * 10 ** token_in.decimals()
        utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, 0)
        assert joint.pendingRewards() == rewards_pending

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

@pytest.mark.parametrize("swap_from", ["a", "b"])
def test_not_enough_liquidity_to_balance_UNIV3(
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
    simulate_swap
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)
    
    utils.univ3_empty_pool_reserve(joint.pool(), swap_from, tokenA, tokenB, router, tokenA_whale, tokenB_whale)
    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    # TODO: Implement alternative way of swapping the rebalance for this case as it gets stuck!
    