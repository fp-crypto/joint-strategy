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

@pytest.fixture
def hedgilV2():
    yield Contract("0x2bBA5035AeBED1d0f546e31C07c462C1ed9B7597")

@pytest.fixture
def chainlink_owner():
    yield accounts.at("0x9ba4c51512752E79317b59AB4577658e12a43f55", force=True)

@pytest.fixture
def deployer(accounts):
    yield accounts.at("0xcc4c922db2ef8c911f37e73c03b632dd1585ad0e", force=True)

@pytest.fixture
def dai():
    yield Contract(token_addresses["DAI"])


token_addresses = {
    "YFI": "0x29b0Da86e484E1C0029B56e817912d778aC0EC69",  # YFI
    "WETH": "0x74b23882a30290451A17c44f4F05243b6b58C76d",  # WETH
    "DAI": "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E",  # DAI
    "USDC": "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # USDC
    "SUSHI": "0xae75A438b2E0cB8Bb01Ec1E1e376De11D44477CC",  # SUSHI
    "MIM": "0x82f0b8b456c1a451378467398982d4834b6829c1", # MIM
    "WFTM": "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", # WFTM
    "SPIRIT": "0x5Cc61A78F164885776AA610fb0FE1257df78E59B", # SPIRIT
    "BOO": "0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE", # BOO
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
        'USDC', # USDC
        # "WFTM", 
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
        'WFTM',
        # "MIM",
    ],
    scope="session",
    autouse=True,
)
def tokenB(request):
    yield Contract(token_addresses[request.param])


whale_addresses = {
    "YFI": "0x29b0Da86e484E1C0029B56e817912d778aC0EC69",
    "WETH": "0x74b23882a30290451A17c44f4F05243b6b58C76d",
    "USDC": "0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682",
    "DAI": "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E",
    "SUSHI": "0xae75A438b2E0cB8Bb01Ec1E1e376De11D44477CC",
    "WFTM": "0x5AA53f03197E08C4851CAD8C92c7922DA5857E5d",
    "MIM": "0x2dd7C9371965472E5A5fD28fbE165007c61439E1",
    "BOO": "0xE0c15e9Fe90d56472D8a43da5D3eF34ae955583C",
}

lp_whales = {
    "BOO": {
        "USDC": {
            "WFTM": "0xE6939A804b3C7570Ff5f36c1f0d886dAD4b4A204"
        }
    }
} 
@pytest.fixture(scope="session", autouse=True)
def lp_whale(rewards, tokenA, tokenB):
    yield lp_whales[rewards.symbol()][tokenA.symbol()][tokenB.symbol()]

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
            "MIM": 24,
            "USDC": 2,
            }
        }

@pytest.fixture
def mc_pid(tokenA, tokenB):
    yield mc_pids[tokenB.symbol()][tokenA.symbol()]


router_addresses = {
    "SUSHI": "",
    "SPIRIT": "0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52",
    "SPOOKY": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
    "BOO": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
}


@pytest.fixture
def router(rewards):
    yield Contract(router_addresses[rewards.symbol()])

# Non-comprehensive, find the full list here to add your own: https://docs.chain.link/docs/fantom-price-feeds/
oracle_addresses = {
    "WFTM": "0xf4766552D15AE4d256Ad41B6cf2933482B0680dc",
    "USDC": "0x2553f4eeb82d5A26427b8d1106C51499CBa5D99c",
    "MIM": "0x28de48D3291F31F839274B8d82691c77DF1c5ceD"
}

@pytest.fixture
def tokenA_oracle(tokenA):
    yield Contract(oracle_addresses[tokenA.symbol()])

@pytest.fixture
def tokenB_oracle(tokenB):
    yield Contract(oracle_addresses[tokenB.symbol()])

@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)

@pytest.fixture
def wftm():
    token_address = token_addresses['WFTM']
    yield Contract(token_address)

@pytest.fixture(params=["BOO"], scope="session", autouse=True)
def rewards(request):
    rewards_address = token_addresses[request.param]  # sushi
    yield Contract(rewards_address)


@pytest.fixture
def rewards_whale(rewards):
    yield whale_addresses[rewards.symbol()]


masterchef_addresses = {
    "SUSHI": "0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd",
    "SPIRIT": "0x9083EA3756BDE6Ee6f27a6e996806FBD37F6F093",
    "BOO": "0x2b2929E785374c651a81A63878Ab22742656DcDd",
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
    SpookyJoint,
    router,
    masterchef,
    rewards,
    wftm,
    mc_pid,
    hedgilV2,
    LPHedgingLibrary,
    gov,
    tokenA,
    tokenB,
):
    gas_price(0)

    joint = gov.deploy(
        SpookyJoint,
        providerA,
        providerB,
        router,
        wftm,
        rewards,
        hedgilV2,
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
                "MIM": "0xC0176FAa0e20dFf3CB6B810aEaE64ef271B1b64b",
                "MIM": "0x150C42e9CB21354030967579702e0f010e208E86",
                "USDC": "0x8C2cC5ff69Bc3760d7Ce81812A2848421495972A",
            }
    }

@pytest.fixture(autouse=True)
def provideLiquidity(hedgilV2, tokenA, tokenB, tokenA_whale, tokenB_whale, amountA, amountB):
    tokenB.approve(hedgilV2, 2 ** 256 - 1, {'from': tokenB_whale, 'gas_price': '0'})
    hedgilV2.provideLiquidity(100_000 * 10 ** tokenB.decimals(), 0, tokenB_whale, {'from': tokenB_whale, 'gas_price': '0'})

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
    ftm_price = reserve0 / reserve1 *  10 ** (9+12)
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
