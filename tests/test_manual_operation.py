from utils import actions, utils, checks

# TODO: check that all manual operation works as expected
# manual operation: those functions that are called by management to affect strategy's position
# e.g. repay debt manually
# e.g. emergency unstake
def test_manual_unwind(
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
):
    # start epoch
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    # let it run to half period
    actions.wait_period_fraction(joint, 0.5)

    # move price by swapping
    actions.swap(
        tokenA,
        tokenB,
        amountA * 5,
        tokenA_whale,
        joint,
        mock_chainlink,
    )

    # manual end of epoch
    # manual unstake
    joint.withdrawLPManually(joint.balanceOfStake(), {"from": gov})
    # manual close hedge
    joint.closeHedgeManually(joint.activeCallID(), joint.activePutID(), {"from": gov})
    # manual remove liquidity
    joint.removeLiquidityManually(joint.balanceOfPair(), 0, 0, {"from": gov})
    # manual rebalance

    # manual return funds to providers
    joint.returnLooseToProvidersManually({"from": gov})
    # manual set not invest want
    joint.setDontInvestWant(True, {"from": gov})
    # return funds to vaults
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert vaultA.strategies(providerA).dict()["totalDebt"] == 0
    assert vaultB.strategies(providerB).dict()["totalDebt"] == 0


def test_manual_stop_invest_want(
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
):
    # start epoch
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    actions.gov_start_epoch(
        gov, providerA, providerB, joint, vaultA, vaultB, amountA, amountB
    )

    # let it run to half period
    actions.wait_period_fraction(joint, 0.5)

    # set dont invest want to true
    joint.setDontInvestWant(True, {"from": gov})
    # set debt ratios to > 0 (to make providers think they should invest)
    vaultA.updateStrategyDebtRatio(providerA, 10_000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10_000, {"from": gov})

    # restart epoch
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert providerA.balanceOfWant() == providerA.estimatedTotalAssets()
    assert providerB.balanceOfWant() == providerB.estimatedTotalAssets()

    assert joint.balanceOfPair() == 0
    assert joint.balanceOfStake() == 0
    assert joint.balanceOfA() == 0
    assert joint.balanceOfB() == 0
