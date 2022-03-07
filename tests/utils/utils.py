import brownie
from brownie import interface, chain, accounts, web3, network, Contract


def sync_price(joint):
    # we update the price on the Oracle to simulate real market dynamics
    # otherwise, price of pair and price of oracle would be different and it would look manipulated
    relayer = "0x33E0E07cA86c869adE3fc9DE9126f6C73DAD105e"
    imp = Contract("0x5bfab94edE2f4d911A6CC6d06fdF2d43aD3c7068")
    lp_token = Contract(joint.pair())
    (reserve0, reserve1, a) = lp_token.getReserves()
    ftm_price = reserve1 / reserve0 *  10 ** 9
    print(f"Current price is: {ftm_price/1e9}")
    imp.relay(["FTM"], [ftm_price], [chain.time()], [4281375], {'from': relayer})

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
def sleep(seconds = 6 * 60 * 60):
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

    if(token0 == tokenB):
        resA = res1
        resB = res0
    print("############ JOINT STATUS ############")
    print(f"Invested tokens in pool: {balA} {tokenA.symbol()} and {balB} {tokenB.symbol()}")
    print(f"Existing reserves in pool: {resA} {tokenA.symbol()} and {resB} {tokenB.symbol()}")
    print(f"Ratio of joint to pool: {balA / resA} {tokenA.symbol()} and {balB / resB} {tokenB.symbol()}")
    print(f"Staked LP tokens: {joint.balanceOfStake()} {lp_token.symbol()}")
    print(f"Total rewards gained: {joint.balanceOfReward() + joint.pendingReward()}")
    print("######################################")

def swap_tokens_value(router, tokenIn, tokenOut, amountIn):
    return router.getAmountsOut(amountIn, [tokenIn, tokenOut])[1]