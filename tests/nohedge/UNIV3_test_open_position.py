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

