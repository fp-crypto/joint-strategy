import pytest
from brownie import chain, Contract
import utils

# This file is reserved for standard actions like deposits
def user_deposit(user, vault, token, amount):
    if token.allowance(user, vault) < amount:
        token.approve(vault, 2 ** 256 - 1, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount


def gov_start_epoch(gov, providerA, providerB, joint, vaultA, vaultB):
    # the first harvest sends funds (tokenA) to joint contract and waits for tokenB funds
    # the second harvest sends funds (tokenB) to joint contract AND invests them (if there is enough TokenA)
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    # we set debtRatio to 0 after starting an epoch to be sure that funds return to vault after each epoch
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})


def gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB):
    # first harvest uninvests (withdraws, closes hedge and removes liquidity) and takes funds (tokenA)
    # second harvest takes funds (tokenB) from joint
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    # we set debtRatio to 10_000 in tests because the two vaults have the same amount.
    # in prod we need to set these manually to represent the same value
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})


def generate_profit(
    amount_percentage, joint, providerA, providerB, tokenA_whale, tokenB_whale
):
    # we just airdrop tokens to the joint
    tokenA = Contract(joint.tokenA())
    tokenB = Contract(joint.tokenB())
    profitA = providerA.estimatedTotalAssets() * amount_percentage
    profitB = providerB.estimatedTotalAssets() * amount_percentage

    tokenA.transfer(joint, profitA, {"from": tokenA_whale})
    tokenB.transfer(joint, profitB, {"from": tokenB_whale})

    return profitA, profitB


def swap(tokenFrom, tokenTo, amountFrom, tokenFrom_whale, joint, mock_chainlink):
    tokenFrom.approve(joint.router(), 2 ** 256 - 1, {"from": tokenFrom_whale})
    print(
        f"Dumping {amountFrom/10**tokenFrom.decimals()} {tokenFrom.symbol()} for {tokenTo.symbol()}"
    )
    reserveA, reserveB = joint.getReserves()
    pairPrice = (
        reserveB
        / reserveA
        * 10 ** Contract(joint.tokenA()).decimals()
        / 10 ** Contract(joint.tokenB()).decimals()
    )
    print(f"OldPairPrice: {pairPrice}")
    router.swapExactTokensForTokens(
        amountFrom,
        0,
        [tokenFrom, tokenTo],
        tokenFrom_whale,
        2 ** 256 - 1,
        {"from": tokenFrom_whale},
    )
    reserveA, reserveB = joint.getReserves()
    pairPrice = (
        reserveB
        / reserveA
        * 10 ** Contract(joint.tokenA()).decimals()
        / 10 ** Contract(joint.tokenB()).decimals()
    )
    print(f"NewPairPrice: {pairPrice}")
    utils.sync_price(joint, mock_chainlink)


# TODO: add args as required
def generate_loss(amount):
    # TODO: add action for simulating profit
    return


def first_deposit_and_harvest(
    vault, strategy, token, user, gov, amount, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest({"from": gov})
    utils.sleep()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
