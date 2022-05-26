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
    before_tick = uni_v3_pool.slot0()["tick"]
    print(f'Pool tick before test: {uni_v3_pool.slot0()["tick"]}')
    assert joint.harvestTrigger() == False
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)
    assert joint.harvestTrigger() == False

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

    assert joint.harvestTrigger() == True
    new_tick = uni_v3_pool.slot0()["tick"]
    assert 0