from pytest import approx
from utils import utils, actions, checks


def test_harvest_trigger_within_period(
    vaultA,
    vaultB,
    providerA,
    providerB,
    tokenA,
    tokenB,
    joint,
    user,
    gov,
    amountA,
    amountB,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    # harvest trigger should return false
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False
    # wait period (just before)
    joint.setMinTimeToMaturity(
        joint.period() * 0.98, {"from": gov}
    )  # to be able to mine less blocks
    actions.wait_period_fraction(joint, 0.02)  # only half time for this

    # harvest trigger should return true
    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    assert joint.shouldEndEpoch() == True

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False


def test_harvest_trigger_after_period(
    vaultA,
    vaultB,
    providerA,
    providerB,
    tokenA,
    tokenB,
    joint,
    user,
    gov,
    amountA,
    amountB,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    # harvest trigger should return false
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False

    actions.wait_period_fraction(joint, 1.01)

    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    assert joint.shouldEndEpoch() == True

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})
    # harvesting should close the epoch
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False


def test_harvest_trigger_below_range(
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    gov,
    tokenA_whale,
    mock_chainlink,
    tokenA,
    tokenB,
    amountA,
    amountB,
):
    # deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    # harvesttrigger should return false

    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False
    # swap a4b (sell tokenA) so the price is out of protected range (below)
    actions.swap(
        tokenA,
        tokenB,
        amountA * 13,
        tokenA_whale,
        joint,
        mock_chainlink,
    )

    # harvestrigger should return true
    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    assert joint.shouldEndEpoch() == True
    # harvesting should close the epoch

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False


def test_harvest_trigger_above_range(
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    gov,
    tokenB_whale,
    mock_chainlink,
    tokenA,
    tokenB,
    amountA,
    amountB,
):
    # deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )
    # harvesttrigger should return false
    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False

    # swap b4a (buy tokenA) so the price is out of protected range (above)
    actions.swap(
        tokenB,
        tokenA,
        amountB * 13,
        tokenB_whale,
        joint,
        mock_chainlink,
    )

    # harvestrigger should return true
    assert providerA.harvestTrigger(1) == True
    assert providerB.harvestTrigger(1) == True
    assert joint.shouldEndEpoch() == True

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})
    # harvesting should close the epoch
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert providerA.harvestTrigger(1) == False
    assert providerB.harvestTrigger(1) == False
    assert joint.shouldEndEpoch() == False
