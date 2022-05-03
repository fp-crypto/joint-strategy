from utils import actions, checks, utils
import pytest
from brownie import Contract, chain, interface
import eth_utils
from eth_abi.packed import encode_abi_packed

# tests harvesting a strategy that returns profits correctly
def test_open_close_position_UNIV3(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    hedge_type,
    dex,
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert vaultA.strategies(providerA).dict()['totalDebt'] == amountA
    assert vaultB.strategies(providerB).dict()['totalDebt'] == amountB

    assert pytest.approx(joint.balanceOfTokensInLP()[0] + tokenA.balanceOf(providerA), rel=RELATIVE_APPROX) == amountA
    assert pytest.approx(joint.balanceOfTokensInLP()[1] + tokenB.balanceOf(providerB), rel=RELATIVE_APPROX) == amountB

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})

    chain.sleep(1)
    chain.mine(1)
    
    txA = providerA.harvest({"from": gov})
    txB = providerB.harvest({"from": gov})

    assert pytest.approx(txA.events["Harvested"]['loss'], rel=RELATIVE_APPROX) == 1
    assert pytest.approx(txB.events["Harvested"]['loss'], rel=RELATIVE_APPROX) == 1

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0


def test_open_close_position_with_swap_UNIV3(
    chain,
    tokenA,
    tokenB,
    vaultA,
    vaultB,
    providerA,
    providerB,
    joint,
    user,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    hedge_type,
    dex,
    uni_v3_pool
):
    checks.check_run_test("nohedge", hedge_type)
    checks.check_run_test("UNIV3", dex)
    
    # Deposit to the vault
    actions.user_deposit(user, vaultA, tokenA, amountA)
    actions.user_deposit(user, vaultB, tokenB, amountB)

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    chain.mine(1)

    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    assert vaultA.strategies(providerA).dict()['totalDebt'] == amountA
    assert vaultB.strategies(providerB).dict()['totalDebt'] == amountB

    assert pytest.approx(joint.balanceOfTokensInLP()[0] + tokenA.balanceOf(providerA), rel=RELATIVE_APPROX) == amountA
    assert pytest.approx(joint.balanceOfTokensInLP()[1] + tokenB.balanceOf(providerB), rel=RELATIVE_APPROX) == amountB

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    univ3_router = Contract("0xE592427A0AEce92De3Edee1F18E0157C05861564")
    sell_amount = 20_000_000 * 10 ** tokenA.decimals()
    tokenA.approve(univ3_router, 2**256-1, {'from': tokenA_whale})
    univ3_router.exactInputSingle(
        (
            tokenA,
            tokenB,
            100,
            tokenB_whale,
            2**256-1,
            sell_amount,
            0,
            0
        ),
        {'from': tokenA_whale}
    )

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())
    print("pending", joint.pendingRewards())

    vaultA.updateStrategyDebtRatio(providerA, 0, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 0, {"from": gov})

    providerA.setDoHealthCheck(False, {"from":gov})
    providerB.setDoHealthCheck(False, {"from":gov})
    
    providerA.harvest({"from": gov})
    providerB.harvest({"from": gov})

    print("etas", providerA.estimatedTotalAssets(), providerB.estimatedTotalAssets())

    assert joint.balanceOfTokensInLP()[0] == 0
    assert joint.balanceOfTokensInLP()[1] == 0

    assert providerA.estimatedTotalAssets() == 0
    assert providerB.estimatedTotalAssets() == 0

