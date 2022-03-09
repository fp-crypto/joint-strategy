from utils import actions, checks, utils
import pytest
from brownie import Contract, chain
import eth_utils
from eth_abi.packed import encode_abi_packed

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
    lp_token,
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

    investedA, investedB = joint.investedA(), joint.investedB()

    txA, txB = actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    profitA = txA.events["Harvested"]["profit"]
    profitB = txB.events["Harvested"]["profit"]
    returnA = profitA / investedA
    returnB = profitB / investedB

    print(f"Return A: {returnA:.4%}")
    print(f"Return B: {returnB:.4%}")

    # Return approximately equal
    assert pytest.approx(returnA, rel=1e-3) == returnB

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
    lp_token,
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

    joint.removeLiquidityManually(joint.balanceOfPair(), 0, 0, {"from": gov})
    joint.returnLooseToProvidersManually({"from": gov})

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


# tests harvesting a strategy that returns profits correctly with a big swap imbalancing
@pytest.mark.parametrize("swap_from", ["a", "b"])
def test_profitable_with_big_imbalance_harvest(
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
    router,
    strategist,
    amountA,
    amountB,
    RELATIVE_APPROX,
    gov,
    tokenA_whale,
    tokenB_whale,
    mock_chainlink,
    lp_token,
    swap_from,
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

    token_in = tokenA if swap_from == "a" else tokenB
    token_in_whale = tokenA_whale if swap_from == "a" else tokenB_whale
    token_in.approve(router, 2 ** 256 - 1, {"from": token_in_whale})
    router.swapExactTokensForTokensSimple(
        10_000_000 * 10 ** token_in.decimals(),
        0,
        token_in,
        tokenB if swap_from == "a" else tokenA,
        True,
        token_in_whale,
        2 ** 256 - 1,
        {"from": token_in_whale},
    )

    investedA, investedB = joint.investedA(), joint.investedB()

    txA, txB = actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    profitA = txA.events["Harvested"]["profit"]
    profitB = txB.events["Harvested"]["profit"]
    returnA = profitA / investedA
    returnB = profitB / investedB

    print(f"Return A: {returnA:.4%}")
    print(f"Return B: {returnB:.4%}")

    # Return approximately equal
    assert pytest.approx(returnA, rel=RELATIVE_APPROX) == returnB

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


# tests harvesting a strategy that returns profits correctly
def test_profitable_harvest_yswaps(
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
    lp_token,
    wftm,
    trade_factory,
    yMechs_multisig,
):
    # TODO: get this ready for solidex
    return
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

    profit_amount_percentage = 0.0
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

    token_out = joint.tokenA()

    receiver = joint.address
    multicall_swapper = Contract("0x590B3e12Ded77dE66CBF45050cD07a65d1F51dDD")

    ins = [solid_token, sex_token]

    for id in ins:
        print(id.address)
        token_in = id

        amount_in = id.balanceOf(joint)
        print(
            f"Executing trade {id}, tokenIn: {token_in.symbol()} -> tokenOut {token_out.symbol()} w/ amount in {amount_in/1e18}"
        )

        asyncTradeExecutionDetails = [joint, token_in, token_out, amount_in, 1]

        # always start with optimisations. 5 is CallOnlyNoValue
        optimsations = [["uint8"], [5]]
        a = optimsations[0]
        b = optimsations[1]

        calldata = token_in.approve.encode_input(solid_router, amount_in)
        t = createTx(token_in, calldata)
        a = a + t[0]
        b = b + t[1]

        calldata = solid_router.swapExactTokensForTokens.encode_input(
            amount_in,
            0,
            [(token_in.address, wftm, False), (wftm, joint.tokenA(), False)],
            receiver,  # "0xB2F65F254Ab636C96fb785cc9B4485cbeD39CDAA",

            2 ** 256 - 1,
        )
        t = createTx(solid_router, calldata)
        a = a + t[0]
        b = b + t[1]

        transaction = encode_abi_packed(a, b)

        # min out must be at least 1 to ensure that the tx works correctly
        # trade_factory.execute["uint256, address, uint, bytes"](
        #    multicall_swapper.address, 1, transaction, {"from": ymechs_safe}
        # )
        trade_factory.execute["tuple,address,bytes"](
            asyncTradeExecutionDetails,
            multicall_swapper,
            transaction,
            {"from": yMechs_multisig, "gas_price": 0},
        )
        print(
            f"Joint {token_out.symbol()} balance: {token_out.balanceOf(joint)/10**token_out.decimals():.6f}"
        )

    solid_post = solid_token.balanceOf(joint)
    sex_post = sex_token.balanceOf(joint)
    assert solid_post == 0
    assert sex_post == 0

    investedA, investedB = joint.investedA(), joint.investedB()

    txA, txB = actions.gov_end_epoch(gov, providerA, providerB, joint, vaultA, vaultB)
    profitA = txA.events["Harvested"]["profit"]
    profitB = txB.events["Harvested"]["profit"]
    lossA = txA.events["Harvested"]["loss"]
    lossB = txB.events["Harvested"]["loss"]
    returnA = profitA / investedA if profitA > 0 else -lossA / investedA
    returnB = profitB / investedB if profitB > 0 else -lossB / investedB

    print(f"Return A: {returnA:.4%}")
    print(f"Return B: {returnB:.4%}")
    assert profitA > 0
    assert profitB > 0

    # Return approximately equal
    assert pytest.approx(returnA, rel=RELATIVE_APPROX) == returnB

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
    assert vaultA.pricePerShare() >= before_pps_tokenA
    assert vaultB.pricePerShare() >= before_pps_tokenB


def createTx(to, data):
    inBytes = eth_utils.to_bytes(hexstr=data)
    return [["address", "uint256", "bytes"], [to.address, len(inBytes), inBytes]]
