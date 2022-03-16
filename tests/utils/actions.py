import pytest
from brownie import chain, Contract, AggregatorMock, accounts
from utils import checks, utils

# This file is reserved for standard actions like deposits
def user_deposit(user, vault, token, amount):
    if token.allowance(user, vault) < amount:
        token.approve(vault, 2**256 - 1, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount


def gov_start_epoch(gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB):
    # the first harvest sends funds (tokenA) to joint contract and waits for tokenB funds
    # the second harvest sends funds (tokenB) to joint contract AND invests them (if there is enough TokenA)
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    # we set debtRatio to 0 after starting an epoch to be sure that funds return to vault after each epoch
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    checks.epoch_started(providerA, providerB, joint, amountA, amountB)


def gov_start_non_hedged_epoch(
    gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
):
    # the first harvest sends funds (tokenA) to joint contract and waits for tokenB funds
    # the second harvest sends funds (tokenB) to joint contract AND invests them (if there is enough TokenA)
    joint.setIsHedgingEnabled(False, True, {"from": gov})
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    # we set debtRatio to 0 after starting an epoch to be sure that funds return to vault after each epoch
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    checks.non_hedged_epoch_started(providerA, providerB, joint, amountA, amountB)


def wait_period_fraction(joint, percentage_of_period):
    seconds = int(joint.getTimeToMaturity() * percentage_of_period)
    print(f"Waiting (and mining) {seconds} seconds")
    utils.sleep_mine(seconds)


def gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB):
    # first harvest uninvests (withdraws, closes hedge and removes liquidity) and takes funds (tokenA)
    # second harvest takes funds (tokenB) from joint
    txA = providerA.harvest({"from": gov})
    txB = providerB.harvest({"from": gov})

    # checks.check_strategy_empty(providerA)
    # checks.check_strategy_empty(providerB)

    # we set debtRatio to 10_000 in tests because the two vaults have the same amount.
    # in prod we need to set these manually to represent the same value
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})

    return txA, txB


def gov_end_non_hedged_epoch(gov, providerA, providerB, joint, vaultA, vaultB):
    # first harvest uninvests (withdraws and removes liquidity) and takes funds (tokenA)
    # second harvest takes funds (tokenB) from joint
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})
    # we set debtRatio to 10_000 in tests because the two vaults have the same amount.
    # in prod we need to set these manually to represent the same value
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})

    checks.non_hedged_epoch_ended(providerA, providerB, joint)


def generate_profit(
    amount_percentage, joint, providerA, providerB, tokenA_whale, tokenB_whale
):
    # we just airdrop tokens to the joint
    tokenA = Contract(joint.tokenA())
    tokenB = Contract(joint.tokenB())
    profitA = providerA.estimatedTotalAssets() * amount_percentage
    profitB = providerB.estimatedTotalAssets() * amount_percentage

    tokenA.transfer(
        joint, profitA, {"from": tokenA_whale, "gas": 6_000_000, "gas_price": 0}
    )
    tokenB.transfer(
        joint, profitB, {"from": tokenB_whale, "gas": 6_000_000, "gas_price": 0}
    )
    chain.mine(1, timedelta=86_400 * 5)

    return profitA, profitB


def swap(tokenFrom, tokenTo, amountFrom, tokenFrom_whale, joint, mock_chainlink):
    tokenFrom.approve(
        joint.router(), 2 ** 256 - 1, {"from": tokenFrom_whale, "gas_price": 0}
    )
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
    router = Contract(joint.router())
    router.swapExactTokensForTokens(
        amountFrom,
        0,
        [tokenFrom, tokenTo],
        tokenFrom_whale,
        2**256 - 1,
        {"from": tokenFrom_whale, "gas_price": 0},
    )
    reserveA, reserveB = joint.getReserves()
    pairPrice = (
        reserveB
        / reserveA
        * 10 ** Contract(joint.tokenA()).decimals()
        / 10 ** Contract(joint.tokenB()).decimals()
    )
    print(f"NewPairPrice: {pairPrice}")
    utils.sync_price(joint)


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


def sync_price(token, lp_token, chainlink_owner, deployer, token_oracle, tokenA_oracle):
    token_mock_oracle = deployer.deploy(AggregatorMock, 0)

    token_oracle.proposeAggregator(
        token_mock_oracle.address,
        {"from": chainlink_owner, "gas": 6_000_000, "gas_price": 0},
    )
    token_oracle.confirmAggregator(
        token_mock_oracle.address,
        {"from": chainlink_owner, "gas": 6_000_000, "gas_price": 0},
    )

    reserve0, reserve1, a = lp_token.getReserves()

    token0 = Contract(lp_token.token0())
    token1 = Contract(lp_token.token1())

    if token == token0:
        reserveA = reserve0
        reserveB = reserve1
        tokenA = token0
        tokenB = token1
    else:
        reserveA = reserve1
        reserveB = reserve0
        tokenA = token1
        tokenB = token0

    pairPrice = (
        reserveB / reserveA * 10 ** tokenA.decimals() / 10 ** tokenB.decimals() * 1e8
    ) * tokenA_oracle.latestAnswer() / 1e8

    token_mock_oracle.setPrice(pairPrice, {"from": accounts[0]})
    print(f"Current price is: {pairPrice/1e8}")


def dump_token(token_whale, tokenFrom, tokenTo, router, amount):
    tokenFrom.approve(router, 2 ** 256 - 1, {"from": token_whale, "gas_price": 0})
    router.swapExactTokensForTokens(
        amount,
        0,
        [tokenFrom, tokenTo],
        token_whale,
        2 ** 256 - 1,
        {"from": token_whale, "gas_price": 0},
    )


def airdrop_rewards(rewards_whale, amount_token, router, rewards, joint, token):
    amount_rewards = utils.swap_tokens_value(router, token, rewards, amount_token)
    print(f"Transferring {amount_rewards} {rewards.symbol()} rewards to joint")
    rewards.transfer(joint, amount_rewards, {"from": rewards_whale})
