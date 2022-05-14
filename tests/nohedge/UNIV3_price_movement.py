import eth_utils
import pytest
from brownie import Contract, chain, interface, history
from eth_abi.packed import encode_abi_packed
from utils import actions, checks, utils


@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["uni", "crv"])
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
    before_tick = uni_v3_pool.slot0()["tick"]
    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    token_out_whale = tokenB_whale if swap_from == "a" else tokenA_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    if uni_v3_pool.token0() == tokenA.address:
        next_tick = current_tick - 1 if swap_from == "a" else current_tick + 1
    else:
        next_tick = current_tick + 1 if swap_from == "a" else current_tick - 1
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1

    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)
    
    sell_amount = 100e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)

    new_tick = uni_v3_pool.slot0()["tick"]
    assert abs(new_tick - current_tick) == n_ticks

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    sell_amount = 1000e6 * 10 ** token_out.decimals()
    limit_price = testing_library.getSqrtRatioAtTick(before_tick) + 1
    utils.univ3_sell_token(token_out, token_in, router, token_out_whale, sell_amount, univ3_pool_fee, limit_price)
    print(f'Pool tick after test: {uni_v3_pool.slot0()["tick"]}')

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["crv"])
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
    before_tick = uni_v3_pool.slot0()["tick"]
    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    token_out_whale = tokenB_whale if swap_from == "a" else tokenA_whale

    current_tick = uni_v3_pool.slot0()["tick"]
    if uni_v3_pool.token0() == tokenA.address:
        next_tick = current_tick - n_ticks if swap_from == "a" else current_tick + n_ticks
    else:
        next_tick = current_tick + n_ticks if swap_from == "a" else current_tick - n_ticks
    
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1

    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)
    
    sell_amount = 1000e6 * 10 ** token_in.decimals()
    
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)

    new_tick = uni_v3_pool.slot0()["tick"]
    assert abs(new_tick - current_tick) == n_ticks

    rewards_pending = joint.pendingRewards()
    
    if joint.maxTick() < new_tick or new_tick < joint.minTick():
        if swap_from == "a":
            assert joint.balanceOfTokensInLP()[1] == 0
        else:
            assert joint.balanceOfTokensInLP()[0] == 0
        sell_amount = 100 * 10 ** token_in.decimals()
        utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount, univ3_pool_fee, 0)
        assert joint.pendingRewards() == rewards_pending

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    # Reset the tick
    sell_amount = 1000e6 * 10 ** token_out.decimals()
    limit_price = testing_library.getSqrtRatioAtTick(before_tick) + 1
    utils.univ3_sell_token(token_out, token_in, router, token_out_whale, sell_amount, univ3_pool_fee, limit_price)
    print(f'Pool tick after test: {uni_v3_pool.slot0()["tick"]}')

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["uni"])
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
    swap_dex,
    uniswap_helper_views,
    RATIO_PRECISION,
    testing_library,
    univ3_pool_fee
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)

    if swap_dex == "uni":
        joint.setUseCRVPool(False, {"from": gov})
    else:
        joint.setUseCRVPool(True, {"from": gov})
    
    before_tick = uni_v3_pool.slot0()["tick"]
    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)
    
    utils.univ3_empty_pool_reserve(joint.pool(), swap_from, tokenA, tokenB, router, tokenA_whale, tokenB_whale, univ3_pool_fee)
    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    assert ~joint.useCRVPool()
    joint.setUseCRVPool(True, {"from": gov})
    assert joint.useCRVPool()

    # Now we can check estimated total balances and ensure they are within limits
    estimated_assets = joint.estimatedTotalAssetsAfterBalance()
    max_loss_tokenA = (1-joint.maxPercentageLoss() / RATIO_PRECISION) * joint.investedA()
    max_loss_tokenB = (1-joint.maxPercentageLoss() / RATIO_PRECISION) * joint.investedB()

    assert estimated_assets[0] >= max_loss_tokenA
    assert estimated_assets[1] >= max_loss_tokenB
    
    if joint.balanceOfTokensInLP()[0]:
        token_in = tokenA
        token_out = tokenB
        token_in_whale = tokenA_whale
    else:
        token_in = tokenB
        token_out = tokenA
        token_in_whale = tokenB_whale

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    
    assert joint.estimatedTotalAssetsAfterBalance() == (0, 0)

    for (vault, strat) in zip([vaultA, vaultB], [providerA, providerB]):
        assert vault.strategies(strat)["totalDebt"] == 0
    
    # Reset the tick
    sell_amount = 1000e6 * 10 ** token_in.decimals()
    limit_price = testing_library.getSqrtRatioAtTick(before_tick) + 1
    utils.univ3_sell_token(token_out, token_in, router, token_in_whale, sell_amount, univ3_pool_fee, limit_price)
    print(f'Pool tick after test: {uni_v3_pool.slot0()["tick"]}')
