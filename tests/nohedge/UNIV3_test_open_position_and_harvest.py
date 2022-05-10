from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, interface
import eth_utils
from eth_abi.packed import encode_abi_packed

# tests harvesting a strategy that returns profits correctly
def test_open_close_position_UNIV3(
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
    hedge_type,
    dex,
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert vaultA.strategies(providerA).dict()['totalDebt'] == amountA
    assert vaultB.strategies(providerB).dict()['totalDebt'] == amountB

    assert pytest.approx(joint.balanceOfTokensInLP()[0] + tokenA.balanceOf(providerA), rel=RELATIVE_APPROX) == amountA
    assert pytest.approx(joint.balanceOfTokensInLP()[1] + tokenB.balanceOf(providerB), rel=RELATIVE_APPROX) == amountB

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})

    chain.sleep(1)
    chain.mine(1)
    
    txA = providerA.harvest({"from": gov})
    txB = providerB.harvest({"from": gov})

    assert pytest.approx(txA.events["Harvested"]['loss'], rel=RELATIVE_APPROX) == 1
    assert pytest.approx(txB.events["Harvested"]['loss'], rel=RELATIVE_APPROX) == 1

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0


def test_open_close_position_with_swap_UNIV3(
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
    router
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert vaultA.strategies(providerA).dict()['totalDebt'] == amountA
    assert vaultB.strategies(providerB).dict()['totalDebt'] == amountB

    assert pytest.approx(joint.balanceOfTokensInLP()[0] + tokenA.balanceOf(providerA), rel=RELATIVE_APPROX) == amountA
    assert pytest.approx(joint.balanceOfTokensInLP()[1] + tokenB.balanceOf(providerB), rel=RELATIVE_APPROX) == amountB

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    sell_amount = 1_000_000 * 10 ** tokenA.decimals()
    # swap 1m from A to B and then from B to A to end up in the original situation
    utils.univ3_sell_token(tokenA, tokenB, router, tokenA_whale, sell_amount)
    sell_amount = 1_000_000 * 10 ** tokenB.decimals()
    utils.univ3_sell_token(tokenB, tokenA, router, tokenB_whale, sell_amount)

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())
    pending_rewards_estimation = joint.pendingRewards()[0] / 10 ** tokenA.decimals() \
        + joint.pendingRewards()[1] / 10 ** tokenB.decimals()
    print("pending", joint.pendingRewards())

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0

    assert joint.pendingRewards() == (0, 0)

    assert pytest.approx(vaultA.strategies(providerA)["totalGain"]  / 10 ** tokenA.decimals() \
         + vaultB.strategies(providerB)["totalGain"] / 10 ** tokenB.decimals()
         , rel=1e-3) == pending_rewards_estimation

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["crv", "uni"])
def test_lossy_harvest_UNIV3(
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

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    
    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)
    print("Reserves: ", reserves)
    sell_amount = 5 / 100 * reserves[0] if swap_from == "a" else 5 / 100 * reserves[1]
    # swap 1m from one token to the other
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount)

    assets_tokenA = providerA.estimatedTotalAssets()
    assets_tokenB = providerB.estimatedTotalAssets()
    
    print("etas", assets_tokenA, assets_tokenB)
    pending_rewards_estimation = joint.pendingRewards()[0] / 10 ** tokenA.decimals() \
        + joint.pendingRewards()[1] / 10 ** tokenB.decimals()
    print("pending", joint.pendingRewards())

    index_rewards = 0 if swap_from == "a" else 1
    assert joint.pendingRewards()[index_rewards] > 0
    assert joint.pendingRewards()[1 - index_rewards] == 0

    assert pending_rewards_estimation > 0
    assert assets_tokenA < amountA
    assert assets_tokenB < amountB

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0

    assert joint.pendingRewards() == (0, 0)

    assert pytest.approx(amountA - vaultA.strategies(providerA)["totalLoss"], rel=RELATIVE_APPROX) == assets_tokenA
    assert pytest.approx(amountB - vaultB.strategies(providerB)["totalLoss"], rel=RELATIVE_APPROX) == assets_tokenB

    utils.univ3_rebalance_pool(reserves, uni_v3_pool, tokenA, tokenB, router, tokenA_whale, tokenB_whale)

@pytest.mark.parametrize("swap_from", ["a", "b"])
@pytest.mark.parametrize("swap_dex", ["crv", "uni"])
def test_choppy_harvest_UNIV3(
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

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB, keep_dr = False)

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    
    reserves = utils.univ3_get_pool_reserves(joint.pool(), tokenA, tokenB)

    percentage_rewards_swap = 5 / 100
    sell_amount = percentage_rewards_swap * reserves[0] if swap_from == "a" else percentage_rewards_swap * reserves[1]
    # swap from one token to the other
    print(f"selling {sell_amount} {token_in.symbol()}")
    print(reserves)
    reserve_out = reserves[1] if swap_from == "a" else reserves[0]
    if sell_amount > reserve_out:
        sell_amount = int(reserve_out * 95 / 100)
    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount)

    assets_tokenA = providerA.estimatedTotalAssets()
    assets_tokenB = providerB.estimatedTotalAssets()
    
    print("etas", assets_tokenA, assets_tokenB)
    pending_rewards_estimation = joint.pendingRewards()[0] / 10 ** tokenA.decimals() \
        + joint.pendingRewards()[1] / 10 ** tokenB.decimals()
    print("pending", joint.pendingRewards())

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    for (vault, strat) in zip([vaultA, vaultB], [providerA, providerB]):
        assert vault.strategies(strat)["totalLoss"] > 0
        assert vault.strategies(strat)["totalGain"] == 0
        assert vault.strategies(strat)["totalDebt"] == 0
    
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB, keep_dr = False)

    # assert 0
    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())
    
    token_in = tokenB if swap_from == "a" else tokenA
    token_out = tokenA if swap_from == "a" else tokenB
    token_in_whale = tokenB_whale if swap_from == "a" else tokenA_whale

    utils.univ3_buy_token(token_out, token_in, router, token_in_whale, sell_amount)

    token_in = tokenA if swap_from == "a" else tokenB
    token_out = tokenB if swap_from == "a" else tokenA
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale

    utils.univ3_sell_token(token_in, token_out, router, token_in_whale, sell_amount)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0

    assert joint.pendingRewards() == (0, 0)

    for (vault, strat) in zip([vaultA, vaultB], [providerA, providerB]):
        assert vault.strategies(strat)["totalLoss"] > 0
        assert vault.strategies(strat)["totalGain"] > 0
        assert vault.strategies(strat)["totalDebt"] == 0
    utils.univ3_rebalance_pool(reserves, uni_v3_pool, tokenA, tokenB, router, tokenA_whale, tokenB_whale)
