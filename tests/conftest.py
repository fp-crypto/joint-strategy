import pytest
from brownie import config, web3
from brownie import Contract, accounts
from brownie.network import gas_price
from brownie.network.gas.strategies import LinearScalingStrategy
from brownie import chain 

# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
@pytest.fixture(scope="function", autouse=True)
def shared_setup(fn_isolation):
    pass


@pytest.fixture(scope="session", autouse=True)
def reset_chain(chain):
    print(f"Initial Height: {chain.height}")
    yield
    print(f"\nEnd Height: {chain.height}")
    print(f"Reset chain")
    chain.reset()
    print(f"Reset Height: {chain.height}")


@pytest.fixture
def gov(accounts):
    accounts[0].transfer("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", 10e18)
    accounts[0].transfer(accounts[0], 10e18)
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture
def strat_ms(accounts):
    yield accounts.at("0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7", force=True)


@pytest.fixture
def user(accounts):
    yield accounts[0]


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


token_addresses = {
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
    "YFI": "0x0bc529c00C6401aEF6D220BE8C6Ea1667F6Ad93e",  # YFI
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",  # LINK
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",  # DAI
    "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
    "SUSHI": "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",  # SUSHI
    "MIM": "0x82f0b8b456c1a451378467398982d4834b6829c1", # MIM
    "WFTM": "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", # WFTM
    "SPIRIT": "0x5Cc61A78F164885776AA610fb0FE1257df78E59B", # SPIRIT
}

# TODO: uncomment those tokens you want to test as want
@pytest.fixture(
    params=[
        # 'WBTC', # WBTC
        # "YFI",  # YFI
        # "WETH",  # WETH
        # 'LINK', # LINK
        # 'USDT', # USDT
        # 'DAI', # DAI
        # 'USDC', # USDC
        "WFTM", 
    ],
    scope="session",
    autouse=True,
)
def tokenA(request):
    yield Contract(token_addresses[request.param])


# TODO: uncomment those tokens you want to test as want
@pytest.fixture(
    params=[
        # 'WBTC', # WBTC
        # "YFI",  # YFI
        # "WETH",  # WETH
        # 'LINK', # LINK
        # 'USDT', # USDT
        # 'DAI', # DAI
        # "USDC",  # USDC
        "MIM",
    ],
    scope="session",
    autouse=True,
)
def tokenB(request):
    yield Contract(token_addresses[request.param])


whale_addresses = {
    "WBTC": "0x28c6c06298d514db089934071355e5743bf21d60",
    "WETH": "0xc564ee9f21ed8a2d8e7e76c085740d5e4c5fafbe",
    "LINK": "0x28c6c06298d514db089934071355e5743bf21d60",
    "YFI": "0x28c6c06298d514db089934071355e5743bf21d60",
    "USDT": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "USDC": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "DAI": "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503",
    "SUSHI": "0xf977814e90da44bfa03b6295a0616a897441acec",
    "WFTM": "0x5AA53f03197E08C4851CAD8C92c7922DA5857E5d",
    "MIM": "0x2dd7C9371965472E5A5fD28fbE165007c61439E1",
}


@pytest.fixture(scope="session", autouse=True)
def tokenA_whale(tokenA):
    yield whale_addresses[tokenA.symbol()]


@pytest.fixture(scope="session", autouse=True)
def tokenB_whale(tokenB):
    yield whale_addresses[tokenB.symbol()]


token_prices = {
    "WBTC": 60_000,
    "WETH": 4_500,
    "LINK": 20,
    "YFI": 30_000,
    "USDT": 1,
    "USDC": 1,
    "DAI": 1,
    "WFTM": 3,
    "MIM": 1,
}


@pytest.fixture(autouse=True)
def amountA(tokenA, tokenA_whale, user):
    # this will get the number of tokens (around $1m worth of token)
    amillion = round(1_000_000 / token_prices[tokenA.symbol()])
    amount = amillion * 10 ** tokenA.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate a whale address
    if amount > tokenA.balanceOf(tokenA_whale):
        amount = tokenA.balanceOf(tokenA_whale)
    tokenA.transfer(
        user, amount, {"from": tokenA_whale, "gas": 6_000_000, "gas_price": 0}
    )
    yield amount


@pytest.fixture(autouse=True)
def amountB(tokenB, tokenB_whale, user):
    # this will get the number of tokens (around $1m worth of token)
    amillion = round(1_000_000 / token_prices[tokenB.symbol()])
    amount = amillion * 10 ** tokenB.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate a whale address
    if amount > tokenB.balanceOf(tokenB_whale):
        amount = tokenB.balanceOf(tokenB_whale)
    tokenB.transfer(
        user, amount, {"from": tokenB_whale, "gas": 6_000_000, "gas_price": 0}
    )
    yield amount

mc_pids = {
        "WFTM": {
            "MIM": 30
            }
        }

@pytest.fixture
def mc_pid(tokenA, tokenB):
    yield mc_pids[tokenA.symbol()][tokenB.symbol()]


router_addresses = {
    "SUSHI": "",
    "SPIRIT": "0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52",
    "SPOOKY": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
}


@pytest.fixture
def router(rewards):
    yield Contract(router_addresses[rewards.symbol()])


@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)

@pytest.fixture
def wftm():
    token_address = token_addresses['WFTM']
    yield Contract(token_address)

@pytest.fixture(params=["SPIRIT"], scope="session", autouse=True)
def rewards(request):
    rewards_address = token_addresses[request.param]  # sushi
    yield Contract(rewards_address)


@pytest.fixture
def rewards_whale(rewards):
    yield whale_addresses[rewards.symbol()]


masterchef_addresses = {
    "SUSHI": "0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd",
    "SPIRIT": "0x9083EA3756BDE6Ee6f27a6e996806FBD37F6F093",
}


@pytest.fixture
def masterchef(rewards):
    yield Contract(masterchef_addresses[rewards.symbol()])


@pytest.fixture
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture(scope="function", autouse=True)
def vaultA(pm, gov, rewards, guardian, management, tokenA):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenA, gov, rewards, "", "", guardian, management, {"from": gov})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture(scope="function", autouse=True)
def vaultB(pm, gov, rewards, guardian, management, tokenB):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenB, gov, rewards, "", "", guardian, management, {"from": gov})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture(scope="session")
def registry():
    yield Contract("")


@pytest.fixture(scope="session")
def live_vaultA(registry, tokenA):
    yield registry.latestVault(tokenA)


@pytest.fixture(scope="session")
def live_vaultB(registry, tokenB):
    yield registry.latestVault(tokenB)


@pytest.fixture
def joint(
    strategist,
    keeper,
    providerA,
    providerB,
    SpiritJoint,
    router,
    masterchef,
    rewards,
    wftm,
    mc_pid,
    LPHedgingLibrary,
    gov,
    tokenA,
    tokenB,
):
    gas_price(0)

    joint = gov.deploy(
        SpiritJoint,
        providerA,
        providerB,
        router,
        wftm,
        rewards,
        hedgil_pools[tokenA.symbol()][tokenB.symbol()],
        masterchef,
        mc_pid,
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(strategist, keeper, vaultA, ProviderStrategy, gov):
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper, {"from": gov})
    vaultA.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    strategy.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov})
    strategy.setDoHealthCheck(False, {"from": gov})
    Contract(strategy.healthCheck()).setlossLimitRatio(1000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16"})
    Contract(strategy.healthCheck()).setProfitLimitRatio(2000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16"})
    yield strategy


@pytest.fixture
def providerB(strategist, keeper, vaultB, ProviderStrategy, gov):
    strategy = strategist.deploy(ProviderStrategy, vaultB)
    strategy.setKeeper(keeper, {"from": gov})
    vaultB.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    strategy.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov})
    strategy.setDoHealthCheck(False, {"from": gov})
    Contract(strategy.healthCheck()).setlossLimitRatio(1000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16"})
    Contract(strategy.healthCheck()).setProfitLimitRatio(2000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16"})
    yield strategy


hedgil_pools = {
        "WFTM" :
            {
                "MIM": "0x150C42e9CB21354030967579702e0f010e208E86"
            }
    }

@pytest.fixture(autouse=True)
def provideLiquidity(tokenA, tokenB, tokenA_whale, tokenB_whale, amountA, amountB):
    hedgil = Contract(hedgil_pools[tokenA.symbol()][tokenB.symbol()])
    tokenB.approve(hedgil, 2 ** 256 - 1, {'from': tokenB_whale, 'gas_price': '0'})
    hedgil.provideLiquidity(100000 * 1e18, 0, tokenB_whale, {'from': tokenB_whale, 'gas_price': '0'})

# @pytest.fixture
# def cloned_strategy(Strategy, vault, strategy, strategist, gov):
#     # TODO: customize clone method and arguments
#     # TODO: use correct contract name (i.e. replace Strategy)
#     cloned_strategy = strategy.cloneStrategy(
#         strategist, {"from": strategist}
#     ).return_value
#     cloned_strategy = Strategy.at(cloned_strategy)
#     vault.revokeStrategy(strategy)
#     vault.addStrategy(cloned_strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
#     yield
#


@pytest.fixture(autouse=False)
def withdraw_no_losses(vault, token, amount, user):
    yield
    if vault.totalSupply() != 0:
        return
    vault.withdraw({"from": user})

    # check that we dont have previously realised losses
    # NOTE: this assumes deposit is `amount`
    assert token.balanceOf(user) >= amount


@pytest.fixture(autouse=True)
def LPHedgingLibrary(LPHedgingLib, gov):
    yield gov.deploy(LPHedgingLib)


@pytest.fixture(scope="session", autouse=True)
def RELATIVE_APPROX():
    yield 1e-5


@pytest.fixture(autouse=False)
def mock_chainlink(AggregatorMock, gov):
    # owner = "0x21f73d42eb58ba49ddb685dc29d3bf5c0f0373ca"

    # priceProvider = Contract("0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419")
    #aggregator = gov.deploy(AggregatorMock, 0)

    # priceProvider.proposeAggregator(
    #    aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    #)
    #priceProvider.confirmAggregator(
    #    aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    #)

    #yield aggregator
    return

@pytest.fixture(autouse=True)
def first_sync(joint):
    relayer = "0x33E0E07cA86c869adE3fc9DE9126f6C73DAD105e"
    imp = Contract("0x5bfab94edE2f4d911A6CC6d06fdF2d43aD3c7068")
    lp_token = Contract(joint.pair())
    (reserve0, reserve1, a) = lp_token.getReserves()
    ftm_price = reserve1 / reserve0 *  10 ** 9
    print(f"Current price is: {ftm_price/1e9}")
    imp.relay(["FTM"], [ftm_price], [chain.time()], [4281375], {'from': relayer})

@pytest.fixture(autouse=True)
def short_period(gov, joint):
    print(f"Current HedgingPeriod: {joint.period()} seconds")
    joint.setHedgingPeriod(86400, {"from": gov})
    joint.setMinTimeToMaturity(86400 / 2, {"from": gov})
    print(f"New HedgingPeriod: {joint.period()} seconds")
    joint.setProtectionRange(500, {"from": gov})


@pytest.fixture(scope="function", autouse=True)
def reset_tenderly_fork():
    gas_price(0)
    # web3.manager.request_blocking("evm_revert", [1])
    yield
