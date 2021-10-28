import pytest
from utils import actions, checks


def test_revoke_strategy_from_vault(
    chain, token, vault, strategy, amount, user, gov, RELATIVE_APPROX
):
    print(f"to be implemeneted")
    # start epoch

    # wait a bit during period

    # revoke from vault

    # In order to pass this tests, you will need to implement prepareReturn.
    # TODO: uncomment the following lines.
    # vault.revokeStrategy(strategy.address, {"from": gov})
    # chain.sleep(1)
    # strategy.harvest({'from': gov})
    # assert pytest.approx(token.balanceOf(vault.address), rel=RELATIVE_APPROX) == amount


def test_revoke_strategy_from_strategy(
    chain, token, vault, strategy, amount, gov, user, RELATIVE_APPROX
):
    print(f"to be implemeneted")
    # start epoch

    # wait a bit

    # move price by trading

    # revoke using set emergency exit


def test_revoke_with_profit(
    chain, token, vault, strategy, amount, user, gov, RELATIVE_APPROX
):

    print(f"to be implemeneted")

    # start epoch

    # wait a bit

    # move price by trading

    # generate profit

    # Revoke strategy
    vault.revokeStrategy(strategy.address, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": gov})
    checks.check_revoked_strategy(vault, strategy)
