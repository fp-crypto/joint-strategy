from utils import actions, checks, utils
import pytest


def test_airdrop(
    chain,
    user,
    gov,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    amountA,
    amountB,
    RELATIVE_APPROX,
    tokenA_whale,
    tokenB_whale,
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    # start epoch
    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assetsA = joint.investedA()
    total_assetsB = joint.investedB()

    cost_of_investmenA = joint.investedA() - joint.estimatedTotalAssetsInToken(tokenA)
    cost_of_investmenB = joint.investedB() - joint.estimatedTotalAssetsInToken(tokenB)

    assert (
        pytest.approx(total_assetsA, rel=RELATIVE_APPROX)
        == amountA - providerA.balanceOfWant()
    )
    assert (
        pytest.approx(total_assetsB, rel=RELATIVE_APPROX)
        == amountB - providerB.balanceOfWant()
    )

    # we airdrop tokens to strategy
    amount_percentage = 0.1  # 10% of current assets
    airdrop_amountA = providerA.estimatedTotalAssets() * amount_percentage
    airdrop_amountB = providerB.estimatedTotalAssets() * amount_percentage

    actions.generate_profit(
        amount_percentage, joint, providerA, providerB, tokenA_whale, tokenB_whale
    )

    # check that estimatedTotalAssets estimates correctly

    assert (
        pytest.approx((airdrop_amountA / 10 ** tokenA.decimals()), rel=RELATIVE_APPROX)
        == joint.balanceOfA() / 10 ** tokenA.decimals()
    )
    assert (
        pytest.approx((airdrop_amountB / 10 ** tokenB.decimals()), rel=RELATIVE_APPROX)
        == joint.balanceOfB() / 10 ** tokenB.decimals()
    )

    # assert airdrop_amountA == joint.balanceOfA()
    # assert airdrop_amountB == joint.balanceOfB()

    before_ppsA = vaultA.pricePerShare()
    before_ppsB = vaultB.pricePerShare()
    # Harvest 2: Realize profit
    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profitA = tokenA.balanceOf(vaultA.address) - amountA  # Profits go to vaultA
    profitB = tokenB.balanceOf(vaultB.address) - amountB  # Profits go to vaultB

    assert tokenA.balanceOf(vaultA) > amountA
    assert tokenB.balanceOf(vaultB) > amountB
    assert vaultA.pricePerShare() > before_ppsA
    assert vaultB.pricePerShare() > before_ppsB


def test_airdrop_provider(chain, gov, tokenA, vaultA, providerA, tokenA_whale):
    # set debtRatio of providerA to 0
    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    assert providerA.balanceOfWant() == 0

    # airdrop token
    airdrop_amountA = 1 * 10 ** tokenA.decimals()

    tokenA.approve(providerA, airdrop_amountA, {"from": tokenA_whale, "gas_price": 0})
    tokenA.transfer(providerA, airdrop_amountA, {"from": tokenA_whale, "gas_price": 0})

    assert providerA.balanceOfWant() == airdrop_amountA

    # harvest and check it has been taken as profit
    before_ppsA = vaultA.pricePerShare()
    hv = providerA.harvest({"from": gov})
    assert hv.events["Harvested"]["profit"] == airdrop_amountA
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    assert vaultA.pricePerShare() > before_ppsA


def test_airdrop_providers(
    chain,
    user,
    gov,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    amountA,
    amountB,
    RELATIVE_APPROX,
    tokenA_whale,
    tokenB_whale,
):
    # start epoch
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_non_hedged_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assetsA = joint.investedA()
    total_assetsB = joint.investedB()

    assert (
        pytest.approx(total_assetsA, rel=RELATIVE_APPROX)
        == amountA - providerA.balanceOfWant()
    )
    assert (
        pytest.approx(total_assetsB, rel=RELATIVE_APPROX)
        == amountB - providerB.balanceOfWant()
    )

    # airdrop token to providerA
    before_providerA_balance = providerA.balanceOfWant()

    amount_percentage = 0.1  # 10% of current assets
    airdrop_amountA = providerA.estimatedTotalAssets() * amount_percentage

    tokenA.approve(providerA, airdrop_amountA, {"from": tokenA_whale, "gas_price": 0})
    tokenA.transfer(providerA, airdrop_amountA, {"from": tokenA_whale, "gas_price": 0})

    assert providerA.balanceOfWant() - before_providerA_balance == airdrop_amountA

    # check that it has been taken as profit for providerA only
    before_ppsA = vaultA.pricePerShare()
    before_ppsB = vaultB.pricePerShare()
    assert before_ppsA == 1 * 10 ** tokenA.decimals()
    assert before_ppsB == 1 * 10 ** tokenB.decimals()
    # Harvest 2: Realize profit
    actions.gov_end_non_hedged_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    assert pytest.approx(
        vaultA.strategies(providerA).dict()["totalGain"], rel=RELATIVE_APPROX
    ) == int(airdrop_amountA)

    chain.mine(1, timedelta=6 * 3600)

    ppsA = vaultA.pricePerShare()
    ppsB = vaultB.pricePerShare()

    assert ppsA > before_ppsA
    assert pytest.approx(ppsB, rel=RELATIVE_APPROX) == before_ppsB
    assert ppsB >= before_ppsB
