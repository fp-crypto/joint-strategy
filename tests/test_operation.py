import brownie
from brownie import Contract
import pytest
from utils import actions, checks


def test_operation(
    chain, accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):

    print(f"Not implememented")
    # start epoch

    # set new debt ratios (100% and 100%)

    # wait for epoch to finish

    # restart epoch

    # wait for epoch to finish

    # end epoch and return funds to vault


# debt ratios should not be increased in the middle of an epoch
def test_increase_debt_ratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    print(f"Not implememented")
    # set debt ratios to 50% and 50%

    # start epoch

    # set debt ratios to 100% and 100%

    # restart epoch


# debt ratios should not be increased in the middle of an epoch
def test_decrease_debt_ratio(
    chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    print(f"Not implememented")
    # start epoch

    # set dent ratios to 50% and 50%

    # restart epoch


def test_sweep(gov, vault, strategy, token, user, amount, weth, weth_amount):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})

    # TODO: If you add protected tokens to the strategy.
    # Protected token doesn't work
    # with brownie.reverts("!protected"):
    #     strategy.sweep(strategy.protectedToken(), {"from": gov})

    before_balance = weth.balanceOf(gov)
    weth.transfer(strategy, weth_amount, {"from": user})
    assert weth.address != strategy.want()
    assert weth.balanceOf(user) == 0
    strategy.sweep(weth, {"from": gov})
    assert weth.balanceOf(gov) == weth_amount + before_balance
