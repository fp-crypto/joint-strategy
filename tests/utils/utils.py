import brownie
from brownie import interface, chain, accounts


def sync_price(joint, mock_chainlink, strategist):
    # we update the price on the Oracle to simulate real market dynamics
    # otherwise, price of pair and price of oracle would be different and it would look manipulated
    reserveA, reserveB = joint.getReserves()
    pairPrice = (
        reserveB
        / reserveA
        * 10 ** Contract(joint.tokenA()).decimals()
        / 10 ** Contract(joint.tokenB()).decimals()
    )
    mock_chainlink.setPrice(pairPrice, {"from": accounts[0]})

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
