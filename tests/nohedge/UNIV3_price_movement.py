import eth_utils
import pytest
from brownie import Contract, chain, interface, history
from eth_abi.packed import encode_abi_packed
from utils import actions, checks, utils
from xxlimited import new


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
    testing_library
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)

    if swap_dex == "uni":
        joint.setUseUniswapPool(True, {"from": gov})
    else:
        joint.setUseUniswapPool(False, {"from": gov})
    
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
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1

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
@pytest.mark.parametrize("swap_dex", ["uni", "crv"])
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
    testing_library
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)

    if swap_dex == "uni":
        joint.setUseUniswapPool(True, {"from": gov})
    else:
        joint.setUseUniswapPool(False, {"from": gov})
    
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
    # limit_price = uniswap_helper_views.getSqrtRatioAtTick(next_tick) + 1 if swap_from == "a" else uniswap_helper_views.getSqrtRatioAtTick(next_tick) - 1
    limit_price = testing_library.getSqrtRatioAtTick(next_tick) + 1

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
    RATIO_PRECISION
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)

    if swap_dex == "uni":
        joint.setUseUniswapPool(True, {"from": gov})
    else:
        joint.setUseUniswapPool(False, {"from": gov})
    
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
    assert joint.useUniswapPool()
    joint.setUseUniswapPool(False, {"from": gov})
    assert ~joint.useUniswapPool()

    # Now we can check estimated total balances and ensure they are within limits
    estimated_assets = joint.estimatedTotalAssetsAfterBalance()
    max_loss_tokenA = (1-joint.maxPercentageLoss() / RATIO_PRECISION) * joint.investedA()
    max_loss_tokenB = (1-joint.maxPercentageLoss() / RATIO_PRECISION) * joint.investedB()

    assert estimated_assets[0] >= max_loss_tokenA
    assert estimated_assets[1] >= max_loss_tokenB

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    
    assert joint.estimatedTotalAssetsAfterBalance() == (0, 0)
    assert pytest.approx(history[-4].events["TokenExchange"]["tokens_sold"], rel=1e-3) == history[-4].events["TokenExchange"]["tokens_bought"]

    for (vault, strat) in zip([vaultA, vaultB], [providerA, providerB]):
        assert vault.strategies(strat)["totalLoss"] > 0
        assert vault.strategies(strat)["totalGain"] == 0
        assert vault.strategies(strat)["totalDebt"] == 0
