from functools import _lru_cache_wrapper
from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, UniV3StablesJoint, reverts, ProviderStrategy

def test_clone_joint(
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
    weth
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    # Clone the deployed joint
    if joint_to_use == UniV3StablesJoint:
        cloned_joint = joint.cloneUniV3StablesJoint(
            providerA,
            providerB,
            weth,
            uni_v3_pool,
            2
        ).return_value
        cloned_joint = UniV3StablesJoint.at(cloned_joint)
    else:
        print("Joint type not included in test!")

    # Try to clone it again
    if joint_to_use == UniV3StablesJoint:
        with reverts():
            cloned_joint.cloneUniV3StablesJoint(
                providerA,
                providerB,
                weth,
                uni_v3_pool,
                2,
                {"from":cloned_joint, "gas_price":0}
            )
    else:
        print("Joint type not included in test!")
    
    # Try to initialize again
    if joint_to_use == UniV3StablesJoint:
        with reverts():
            cloned_joint.initialize(
                providerA,
                providerB,
                weth,
                uni_v3_pool,
                2,
                {"from":providerA, "gas_price":0}
            )
    else:
        print("Joint type not included in test!")

def test_clone_provider_migrate(
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
    weth
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)
    
    # Harvest 1: Send funds through the strategy
    chain.mine(1, timedelta = 100)
    actions.gov_start_epoch_univ3(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB)

    balanceA_pre = tokenA.balanceOf(providerA)
    balanceB_pre = tokenB.balanceOf(providerB)

    new_providerA = providerA.clone(vaultA).return_value
    new_providerA = ProviderStrategy.at(new_providerA)
    vaultA.migrateStrategy(providerA, new_providerA, {"from":vaultA.governance()})
    new_providerA.setHealthCheck("0xDDCea799fF1699e98EDF118e0629A974Df7DF012", {"from": gov, "gas_price":0})
    new_providerA.setDoHealthCheck(False, {"from": gov, "gas_price":0})

    new_providerB = providerA.clone(vaultB).return_value
    new_providerB = ProviderStrategy.at(new_providerB)
    vaultB.migrateStrategy(providerB, new_providerB, {"from":vaultB.governance()})
    new_providerB.setHealthCheck("0xDDCea799fF1699e98EDF118e0629A974Df7DF012", {"from": gov, "gas_price":0})
    new_providerB.setDoHealthCheck(False, {"from": gov, "gas_price":0})

    # setup joint
    new_providerA.setJoint(joint, {"from": gov})
    new_providerB.setJoint(joint, {"from": gov})

    # Previous providers are empty
    assert tokenA.balanceOf(providerA) == 0
    assert tokenB.balanceOf(providerB) == 0

    # All balance should be in new providers
    assert tokenA.balanceOf(new_providerA) == balanceA_pre
    assert tokenB.balanceOf(new_providerB) == balanceB_pre

    # Joint is interacting with new providers
    assert joint.providerA() == new_providerA
    assert joint.providerB() == new_providerB

    with reverts():
        providerA.harvest({"from": gov})
    with reverts():
        providerB.harvest({"from": gov})
    
    actions.gov_end_epoch(gov, new_providerA, new_providerB, joint, vaultA, vaultB)

    assert providerA.estimatedTotalAssets() == 0
    assert new_providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0
    assert new_providerB.estimatedTotalAssets() == 0

    assert vaultA.strategies(providerA).dict()["totalLoss"] == 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] == 0
    assert vaultA.strategies(new_providerA).dict()["totalLoss"] > 0
    assert vaultB.strategies(new_providerB).dict()["totalLoss"] > 0

    