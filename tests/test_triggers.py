from pytest import approx
from utils import utils, actions, checks


def test_harvest_trigger_within_period(
    vaultA, vaultB, providerA, providerB, joint, user, gov
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    # harvest trigger should return false

    # wait period (just before)

    # harvest trigger should return true

    # harvesting should close the epoch


def test_harvest_trigger_after_period(
    vaultA, vaultB, providerA, providerB, joint, user, gov
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    # harvest trigger should return false

    # wait period (just after it finishes)

    # harvest trigger should return true

    # harvesting should close the epoch


def test_harvest_trigger_below_range():
    print("tobeimplemented")

    # deposit to the vault

    # start epoch

    # harvesttrigger should return false

    # swap a4b (sell tokenA) so the price is out of protected range (below)

    # harvestrigger should return true

    # harvesting should close the epoch


def test_harvest_trigger_above_range():
    print("tobeimplemented")

    # deposit to the vault

    # start epoch

    # harvesttrigger should return false

    # swap b4a (buy tokenA) so the price is out of protected range (above)

    # harvestrigger should return true

    # harvesting should close the epoch
