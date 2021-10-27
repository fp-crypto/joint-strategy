import brownie
import pytest
from brownie import Contract, Wei


def test_sweep(gov, joint, tokenA, tokenB, sushi, sushi_whale):
    with brownie.reverts():
        joint.sweep(tokenA, {"from": gov})
    with brownie.reverts():
        joint.sweep(tokenB, {"from": gov})

    before_bal = sushi.balanceOf(gov)
    amount = 1e18
    sushi.transfer(joint, amount, {"from": sushi_whale})
    joint.sweep(sushi, {"from": gov})
    assert sushi.balanceOf(gov) == before_bal + amount
