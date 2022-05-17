import brownie
from brownie import interface, chain, accounts, web3, network, Contract
import iniconfig


def sync_price(joint):
    # we update the price on the Oracle to simulate real market dynamics
    # otherwise, price of pair and price of oracle would be different and it would look manipulated
    relayer = "0x33E0E07cA86c869adE3fc9DE9126f6C73DAD105e"
    imp = Contract("0x5bfab94edE2f4d911A6CC6d06fdF2d43aD3c7068")
    lp_token = Contract(joint.pair())
    (reserve0, reserve1, a) = lp_token.getReserves()
    ftm_price = reserve1 / reserve0 * 10 ** 9

    print(f"Current price is: {ftm_price/1e9}")
    imp.relay(["FTM"], [ftm_price], [chain.time()], [4281375], {"from": relayer})


def print_hedge_status(joint, tokenA, tokenB):
    callID = joint.activeCallID()
    putID = joint.activePutID()
    callProvider = Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d")
    putProvider = Contract("0x790e96E7452c3c2200bbCAA58a468256d482DD8b")
    callInfo = callProvider.options(callID)
    putInfo = putProvider.options(putID)
    assert (joint.activeCallID() != 0) & (joint.activePutID() != 0)
    (callPayout, putPayout) = joint.getHedgeProfit()
    print(f"Bought two options:")
    print(f"CALL #{callID}")
    print(f"\tStrike {callInfo[1]/1e8}")
    print(f"\tAmount {callInfo[2]/1e18}")
    print(f"\tTTM {(callInfo[4]-chain.time())/3600}h")
    costCall = (callInfo[5] + callInfo[6]) / 0.8
    print(f"\tCost {(callInfo[5]+callInfo[6])/0.8/1e18} {tokenA.symbol()}")
    print(f"\tPayout: {callPayout/1e18} {tokenA.symbol()}")
    print(f"PUT #{putID}")
    print(f"\tStrike {putInfo[1]/1e8}")
    print(f"\tAmount {putInfo[2]/1e18}")
    print(f"\tTTM {(putInfo[4]-chain.time())/3600}h")
    costPut = (putInfo[5] + putInfo[6]) / 0.8
    print(f"\tCost {costPut/1e6} {tokenB.symbol()}")
    print(f"\tPayout: {putPayout/1e6} {tokenB.symbol()}")
    return (costCall, costPut)


def print_hedgil_status(joint, hedgil, tokenA, tokenB):
    print("############ HEDGIL V2 STATUS ############")

    hedgil_id = joint.activeHedgeID()
    hedgil_position = hedgil.getHedgilByID(hedgil_id)

    strike = hedgil_position["strike"]
    print(f"Strike price: {strike} {tokenA.symbol()} / {tokenB.symbol()}")
    current_price = hedgil.getCurrentPrice(tokenA)
    print(f"Current price: {current_price} {tokenA.symbol()} / {tokenB.symbol()}")
    price_movement = current_price / strike - 1
    print(f"Price has moved {100 * price_movement} %")
    max_price_change = hedgil_position["maxPriceChange"] / 1e4
    print(f"Max price movement covered is {max_price_change * 100} %")
    current_payout = hedgil.getCurrentPayout(hedgil_id)
    print(f"Current hedgil payout is: {current_payout} {tokenB.symbol()}")
    ttm = hedgil.getTimeToMaturity(hedgil_id)
    print(f"Remaining time to maturity is {ttm} seconds, or {ttm / 60 / 60} hours")

    print("######################################")


def vault_status(vault):
    print(f"--- Vault {vault.name()} ---")
    print(f"API: {vault.apiVersion()}")
    print(f"TotalAssets: {to_units(vault, vault.totalAssets())}")
    print(f"PricePerShare: {to_units(vault, vault.pricePerShare())}")
    print(f"TotalSupply: {to_units(vault, vault.totalSupply())}")


def strategy_status(vault, strategy):
    status = vault.strategies(strategy).dict()
    print(f"--- Strategy {strategy.name()} ---")
    print(f"Performance fee {status['performanceFee']}")
    print(f"Debt Ratio {status['debtRatio']}")
    print(f"Total Debt {to_units(vault, status['totalDebt'])}")
    print(f"Total Gain {to_units(vault, status['totalGain'])}")
    print(f"Total Loss {to_units(vault, status['totalLoss'])}")


def to_units(token, amount):
    return amount / (10 ** token.decimals())


def from_units(token, amount):
    return amount * (10 ** token.decimals())


# default: 6 hours (sandwich protection)
def sleep(seconds=6 * 60 * 60):
    chain.sleep(seconds)
    chain.mine(1)


def sleep_mine(seconds=13.15):
    start = chain.time()
    blocks = int(seconds / 13.15)
    if network.show_active() == "tenderly":
        method = "evm_increaseBlocks"
        print(f"Block number: {web3.eth.block_number}")
        params = blocks
        web3.manager.request_blocking(method, [params])
        print(f"Block number: {web3.eth.block_number}")
    else:
        chain.mine(blocks)

    end = chain.time()
    print(f"Mined {blocks} blocks during {end-start} seconds")
    chain.sleep(seconds - (end - start))
    chain.mine(1)


def print_joint_status(joint, tokenA, tokenB, lp_token, rewards):
    token0 = lp_token.token0()
    (balA, balB) = joint.balanceOfTokensInLP()
    (res0, res1, _) = lp_token.getReserves()

    resA = res0
    resB = res1

    if token0 == tokenB:
        resA = res1
        resB = res0
    print("############ JOINT STATUS ############")
    print(
        f"Invested tokens in pool: {balA} {tokenA.symbol()} and {balB} {tokenB.symbol()}"
    )
    print(
        f"Existing reserves in pool: {resA} {tokenA.symbol()} and {resB} {tokenB.symbol()}"
    )
    print(
        f"Ratio of joint to pool: {balA / resA} {tokenA.symbol()} and {balB / resB} {tokenB.symbol()}"
    )
    print(f"Staked LP tokens: {joint.balanceOfStake()} {lp_token.symbol()}")
    print(f"Total rewards gained: {joint.balanceOfReward() + joint.pendingReward()}")
    print("######################################")


def swap_tokens_value(router, tokenIn, tokenOut, amountIn):
    return router.getAmountsOut(amountIn, [tokenIn, tokenOut])[1]

def univ3_get_position_info(pool, joint):
    from eth_abi.packed import encode_abi_packed
    from Crypto.Hash import keccak

    k = keccak.new(digest_bits=256)
    k.update(encode_abi_packed(["address", "int24", "int24"], [joint.address, joint.minTick(), joint.maxTick()]))
    return pool.positions(k.hexdigest())

def univ3_sell_token(token_to_sell, token_to_receive, router, whale, amount, fee, limit_price = 0):
    token_to_sell.approve(router, 0, {'from': whale})
    token_to_sell.approve(router, 2**256-1, {'from': whale})
    router.exactInputSingle(
        (
            token_to_sell,
            token_to_receive,
            fee,
            whale,
            2**256-1,
            amount,
            0,
            limit_price
        ),
        {'from': whale}
    )

def univ3_buy_token(token_to_buy, token_to_sell, router, whale, amount, fee, limit_price = 0):
    token_to_sell.approve(router, 0, {'from': whale})
    token_to_sell.approve(router, 2**256-1, {'from': whale})
    router.exactOutputSingle(
        (
            token_to_sell,
            token_to_buy,
            fee,
            whale,
            2**256-1,
            amount,
            2**255-1,
            limit_price
        ),
        {'from': whale}
    )

def univ3_get_pool_reserves(pool, tokenA, tokenB):
    return (tokenA.balanceOf(pool), tokenB.balanceOf(pool))

def univ3_empty_pool_reserve(pool, swap_from, tokenA, tokenB, router, tokenA_whale, tokenB_whale, fee):
    reserves = univ3_get_pool_reserves(pool, tokenA, tokenB)
    buy_amount = reserves[0] - 500_000 * 10**tokenA.decimals() if swap_from == "a" else reserves[1] - 500_000 * 10**tokenB.decimals()
    
    token_in = tokenB if swap_from == "a" else tokenA
    token_out = tokenA if swap_from == "a" else tokenB
    whale = tokenB_whale if swap_from == "a" else tokenA_whale

    token_in.approve(router, 0, {'from': whale})
    token_in.approve(router, 2**256-1, {'from': whale})
    router.exactOutputSingle(
        (
            token_in,
            token_out,
            fee,
            whale,
            2**256-1,
            buy_amount,
            2**256 -1 ,
            0
        ),
        {'from': whale}
    )

def univ3_rebalance_pool(reserves, pool, tokenA, tokenB, router, tokenA_whale, tokenB_whale, univ3_pool_fee):
    initial_ratio = reserves[0] / reserves[1]
    current_reserves = univ3_get_pool_reserves(pool, tokenA, tokenB)
    current_ratio = current_reserves[0] / current_reserves[1]
    
    if current_ratio > initial_ratio:
        token_in = tokenB
        token_out = tokenA
        whale = tokenB_whale
        amount = (current_reserves[0] - initial_ratio * current_reserves[1]) / (1 + initial_ratio)
    else:
        token_in = tokenA
        token_out = tokenB
        whale = tokenA_whale
        amount = (-current_reserves[0] + initial_ratio * current_reserves[1]) / (1 + initial_ratio)
    univ3_sell_token(token_in, token_out, router, whale, amount, univ3_pool_fee, 0)

def get_crv_index(crv_pool, token):
    if crv_pool.coins(0) == token.address:
        return 0
    elif crv_pool.coins(1) == token.address:
        return 1
    elif crv_pool.coins(2) == token.address:
        return 2

def crv_ensure_bad_trade(crv_pool, token_in, token_out, token_in_whale):
    crv_pool = Contract(crv_pool)
    index_from = get_crv_index(crv_pool, token_in)
    index_to = get_crv_index(crv_pool, token_out)
    
    reserve_token_from = crv_pool.balances(index_from)
    reserve_token_to = crv_pool.balances(index_to)
    sell_amount = reserve_token_to / 2
    sell_amount = sell_amount / (10**token_out.decimals()) * (10**token_in.decimals())

    token_in.approve(crv_pool, 0, {"from": token_in_whale})
    token_in.approve(crv_pool, 2**256-1, {"from": token_in_whale})
    crv_pool.exchange(index_from, index_to, sell_amount, 0, {"from": token_in_whale})

    return reserve_token_to

def crv_re_peg_pool(crv_pool, token_in, token_out, token_in_whale, previous_reserve):
    crv_pool = Contract(crv_pool)
    index_from = get_crv_index(crv_pool, token_in)
    index_to = get_crv_index(crv_pool, token_out)
    
    reserve_token_from = crv_pool.balances(index_from)
    sell_amount = previous_reserve - reserve_token_from

    token_in.approve(crv_pool, 0, {"from": token_in_whale})
    token_in.approve(crv_pool, 2**256-1, {"from": token_in_whale})
    crv_pool.exchange(index_from, index_to, sell_amount, 0, {"from": token_in_whale, "gas_price":0})

def set_max_losses(providerA, providerB, joint, gov, RATIO_PRECISION):
    max_lossA = 1+int(-(providerA.estimatedTotalAssets() / providerA.totalDebt() -1)*100)
    max_lossB = 1+int(-(providerB.estimatedTotalAssets() / providerB.totalDebt() -1)*100)
    
    joint.setMaxPercentageLoss(max(max_lossA, max_lossB) * RATIO_PRECISION / 100, {"from":gov})
