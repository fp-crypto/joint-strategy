from utils import actions, checks, utils
import pytest
from brownie import Contract, chain

# tests harvesting a strategy that returns profits correctly
def test_profitable_harvest(
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
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    solid_token,
    sex_token,
    solid_router,
    lp_token,
    lp_depositor_solidex
):
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assets_tokenA = providerA.estimatedTotalAssets()
    total_assets_tokenB = providerB.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-2) == amountB

    profit_amount_percentage = 0.0095
    profit_amount_tokenA, profit_amount_tokenB = actions.generate_profit(
        profit_amount_percentage,
        joint,
        providerA,
        providerB,
        tokenA_whale,
        tokenB_whale,
    )
    
    before_pps_tokenA = vaultA.pricePerShare()
    before_pps_tokenB = vaultB.pricePerShare()
    # Harvest 2: Realize profit
    chain.sleep(1)

    actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)

    solid_pre = solid_token.balanceOf(joint)
    sex_pre = sex_token.balanceOf(joint)
    assert sex_pre > 0
    assert solid_pre > 0

    gov_solid_pre = solid_token.balanceOf(gov)
    gov_sex_pre = sex_token.balanceOf(gov)
    joint.sweep(solid_token,{"from":gov})

    joint.sweep(sex_token,{"from":gov})
    
    assert (solid_token.balanceOf(gov) - gov_solid_pre) == solid_pre
    assert (sex_token.balanceOf(gov) - gov_sex_pre) == sex_pre

    utils.sleep()  # sleep for 6 hours

    # all the balance (principal + profit) is in vault
    total_balance_tokenA = vaultA.totalAssets()
    total_balance_tokenB = vaultB.totalAssets()
    assert (
        pytest.approx(total_balance_tokenA, rel=5 * 1e-3)
        == amountA + profit_amount_tokenA
    )
    assert (
        pytest.approx(total_balance_tokenB, rel=5 * 1e-3)
        == amountB + profit_amount_tokenB
    )
    assert vaultA.pricePerShare() > before_pps_tokenA
    assert vaultB.pricePerShare() > before_pps_tokenB

# tests harvesting manually
def test_manual_exit(
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
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    solid_token,
    sex_token,
    solid_router,
    lp_token,
    lp_depositor_solidex
):
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    total_assets_tokenA = providerA.estimatedTotalAssets()
    total_assets_tokenB = providerB.estimatedTotalAssets()

    assert pytest.approx(total_assets_tokenA, rel=1e-2) == amountA
    assert pytest.approx(total_assets_tokenB, rel=1e-2) == amountB

    profit_amount_percentage = 0.0095
    profit_amount_tokenA, profit_amount_tokenB = actions.generate_profit(
        profit_amount_percentage,
        joint,
        providerA,
        providerB,
        tokenA_whale,
        tokenB_whale,
    )
    
    before_pps_tokenA = vaultA.pricePerShare()
    before_pps_tokenB = vaultB.pricePerShare()
    # Harvest 2: Realize profit
    chain.sleep(1)

    joint.claimRewardManually()
    joint.withdrawLPManually(joint.balanceOfStake())

    joint.removeLiquidityManually(joint.balanceOfPair(), 0, 0, {"from":gov})
    joint.returnLooseToProvidersManually({"from":gov})

    solid_pre = solid_token.balanceOf(joint)
    sex_pre = sex_token.balanceOf(joint)
    assert sex_pre > 0
    assert solid_pre > 0

    gov_solid_pre = solid_token.balanceOf(gov)
    gov_sex_pre = sex_token.balanceOf(gov)
    joint.sweep(solid_token,{"from":gov})

    joint.sweep(sex_token,{"from":gov})
    
    assert (solid_token.balanceOf(gov) - gov_solid_pre) == solid_pre
    assert (sex_token.balanceOf(gov) - gov_sex_pre) == sex_pre

    assert tokenA.balanceOf(providerA) > amountA
    assert tokenB.balanceOf(providerB) > amountB

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.harvest()
    providerB.harvest()

    assert vaultA.strategies(providerA).dict()["totalGain"] > 0
    assert vaultA.strategies(providerA).dict()["totalLoss"] == 0
    assert vaultA.strategies(providerA).dict()["totalDebt"] == 0

    assert vaultB.strategies(providerB).dict()["totalGain"] > 0
    assert vaultB.strategies(providerB).dict()["totalLoss"] == 0
    assert vaultB.strategies(providerB).dict()["totalDebt"] == 0