import brownie
import pytest
from brownie import Contract, Wei
from utils import sync_price


def test_joint_migration(
    gov,
    strategist,
    weth,
    vaultA,
    vaultB,
    joint,
    providerA,
    providerB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    tokenA_whale,
    tokenB_whale,
    SushiJoint,
    mock_chainlink,
):
    sync_price(joint, mock_chainlink, strategist)
    old_joint = joint
    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    old_joint.liquidatePosition({"from": gov})
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert old_joint.balanceOfB() + old_joint.balanceOfA() == 0
    assert old_joint.balanceOfPair() + old_joint.balanceOfStake() == 0

    new_joint = SushiJoint.deploy(
        providerA,
        providerB,
        joint.router(),
        weth,
        joint.masterchef(),
        joint.reward(),
        joint.pid(),
        {"from": gov},
    )

    providerA.setJoint(new_joint, {"from": gov})
    providerB.setJoint(new_joint, {"from": gov})

    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})

    assert providerA.takeProfit() == False
    assert providerB.takeProfit() == False

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert new_joint.balanceOfStake() > 0


def test_joint_clone_migration(
    chain,
    gov,
    strategist,
    weth,
    vaultA,
    vaultB,
    joint,
    providerA,
    providerB,
    tokenA,
    tokenB,
    amountA,
    amountB,
    tokenA_whale,
    tokenB_whale,
    SushiJoint,
    mock_chainlink,
):
    sync_price(joint, mock_chainlink, strategist)
    old_joint = joint
    tokenA.approve(vaultA, 2 ** 256 - 1, {"from": tokenA_whale})
    vaultA.deposit(amountA, {"from": tokenA_whale})

    tokenB.approve(vaultB, 2 ** 256 - 1, {"from": tokenB_whale})
    vaultB.deposit(amountB, {"from": tokenB_whale})

    chain.sleep(1)
    chain.mine()

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    old_joint.liquidatePosition({"from": gov})
    providerA.setInvestWant(False, {"from": strategist})
    providerB.setInvestWant(False, {"from": strategist})
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert providerA.balanceOfWant() > 0
    assert providerB.balanceOfWant() > 0
    assert old_joint.balanceOfB() + old_joint.balanceOfA() == 0
    assert old_joint.balanceOfPair() + old_joint.balanceOfStake() == 0

    new_joint = SushiJoint.at(
        old_joint.cloneJoint(
            providerA,
            providerB,
            joint.router(),
            weth,
            joint.masterchef(),
            joint.reward(),
            joint.pid(),
            {"from": gov},
        ).return_value
    )
    assert new_joint.balanceOfPair() + new_joint.balanceOfStake() == 0

    providerA.setJoint(new_joint, {"from": gov})
    providerB.setJoint(new_joint, {"from": gov})

    providerA.setInvestWant(True, {"from": strategist})
    providerB.setInvestWant(True, {"from": strategist})

    assert providerA.takeProfit() == False
    assert providerB.takeProfit() == False

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert new_joint.balanceOfStake() > 0
