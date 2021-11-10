import brownie
from brownie import Contract
import pytest
from utils import actions, checks, utils


def test_operation(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
):
    # run two epochs

    # start epoch
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    assert joint.getTimeToMaturity() > 0

    # we set back the debt ratios
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})

    # wait for epoch to finish
    actions.wait_period_fraction(joint, 0.75)

    # restart epoch
    # using start epoch because it is the same and start sets debt ratios to 0
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    assert joint.getTimeToMaturity() > 0

    # wait for epoch to finish
    actions.wait_period_fraction(joint, 0.75)

    # end epoch and return funds to vault
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert providerA.balanceOfWant() == 0


# debt ratios should not be increased in the middle of an epoch
def test_increase_debt_ratio(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
):
    # set debt ratios to 50% and 50%
    vaultA.updateStrategyDebtRatio(providerA, 5_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 5_000, {"from": gov})

    # start epoch
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # to avoid autoprotect due to time to maturitiy
    joint.setAutoProtectionDisabled(True, {"from": gov})

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA / 2, amountB / 2
    )

    # set debt ratios to 100% and 100%
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    # restart epoch
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert vaultA.strategies(providerA).dict()["totalDebt"] == 0
    assert vaultB.strategies(providerB).dict()["totalDebt"] == 0


# debt ratios should not be increased in the middle of an epoch
def test_decrease_debt_ratio(
    chain,
    accounts,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
):
    # start epoch

    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    # to avoid autoprotect due to time to maturitiy
    joint.setAutoProtectionDisabled(True, {"from": gov})
    # set debt ratios to 50% and 50%
    vaultA.updateStrategyDebtRatio(providerA, 5_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 5_000, {"from": gov})

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    # restart epoch
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA / 2, amountB / 2
    )

    providerA.setDoHealthCheck(False, {"from": gov})
    providerB.setDoHealthCheck(False, {"from": gov})

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    assert vaultA.strategies(providerA).dict()["totalDebt"] == 0
    assert vaultB.strategies(providerB).dict()["totalDebt"] == 0
