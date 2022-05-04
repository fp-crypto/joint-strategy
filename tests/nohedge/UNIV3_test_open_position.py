from datetime import timedelta
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain
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
    tokenA_whale,
    tokenB_whale,
    hedge_type,
    dex,
    uni_v3_pool
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    pool = Contract(joint.pool())

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    
    assert pytest.approx(joint.balanceOfTokensInLP()[0] + tokenA.balanceOf(providerA), rel=RELATIVE_APPROX) == amountA
    assert pytest.approx(joint.balanceOfTokensInLP()[1] + tokenB.balanceOf(providerB), rel=RELATIVE_APPROX) == amountB

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0

def test_profitable_harvest(
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
    uni_v3_pool
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    pool = Contract(uni_v3_pool)

    # Check that tick spacing is correct
    assert (joint.maxTick() - joint.minTick()) == (2*joint.ticksFromCurrent()+1) * pool.tickSpacing()

    initial_slot0 = pool.slot0()

    #  Get initial position
    initial_position = utils.univ3_get_position_info(pool, joint)
    initial_slot0 = pool.slot0()[0]

    assert initial_position["tokensOwed0"] == 0
    assert initial_position["tokensOwed1"] == 0

    zero_for_one = True if tokenA.address < tokenB.address else False
    MIN_SQRT_RATIO = 4295128739
    MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
    limit = MIN_SQRT_RATIO + 1 if zero_for_one else MAX_SQRT_RATIO - 1
    # actions.whale_drop_tokenA()

    
    swap_router = Contract("0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45")
    tokenA.approve(swap_router, 2 ** 254, {"from":tokenA_whale, "gas_price":0})

    uni_v3_path = encode_abi_packed(["address", "uint24", "address"], 
        [tokenA.address, pool.fee(), tokenB.address])
    i = 0
    while i < 5:
        swap_router.exactInput((uni_v3_path, tokenA_whale, 1e12, 0), {"from": tokenA_whale, "gas_price":0})
        i+=1

    assert pool.slot0()[0] != initial_slot0
    assert 0
    new_position = utils.univ3_get_position_info(pool, joint)
    assert (new_position["tokensOwed0"] > 0 or new_position["tokensOwed1"] > 0)
