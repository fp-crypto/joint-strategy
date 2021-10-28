from utils import actions
from utils import utils

# TODO: check that all manual operation works as expected
# manual operation: those functions that are called by management to affect strategy's position
# e.g. repay debt manually
# e.g. emergency unstake
def test_manual_unwind(
    chain, token, vault, strategy, amount, gov, user, management, RELATIVE_APPROX
):
    print(f"Not implemented")
    # start epoch

    # let it run to half period

    # move price by swapping

    # manual end of epoch
    # manual unstake
    # manual close hedge
    # manual remove liquidity
    # manual rebalance
    # manual return funds to providers

    # manual set not invest want

    # return funds to vaults


def test_manual_stop_invest_want():
    print(f"Not implemented")
    # start epoch

    # let it run

    # set dont invest want to true

    # set debt ratios to > 0 (to make providers think they should invest)

    # restart epoch
