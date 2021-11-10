import pytest
from brownie import config, web3
from brownie import Contract, accounts
from brownie.network import gas_price
from brownie.network.gas.strategies import LinearScalingStrategy

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
}

# TODO: uncomment those tokens you want to test as want
@pytest.fixture(
    params=[
        # 'WBTC', # WBTC
        # "YFI",  # YFI
        "WETH",  # WETH
        # 'LINK', # LINK
        # 'USDT', # USDT
        # 'DAI', # DAI
        # 'USDC', # USDC
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
        "USDC",  # USDC
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


@pytest.fixture
def mc_pid():
    yield 1


router_addresses = {
    "SUSHI": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
}


@pytest.fixture
def router(rewards):
    yield Contract(router_addresses[rewards.symbol()])


@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)


@pytest.fixture(params=["SUSHI"], scope="session", autouse=True)
def rewards(request):
    rewards_address = token_addresses[request.param]  # sushi
    yield Contract(rewards_address)


@pytest.fixture
def rewards_whale(rewards):
    yield whale_addresses[rewards.symbol()]


masterchef_addresses = {
    "SUSHI": "0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd",
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
    yield Contract("0x50c1a2eA0a861A967D9d0FFE2AE4012c2E053804")


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
    SushiJoint,
    router,
    masterchef,
    rewards,
    weth,
    mc_pid,
    LPHedgingLibrary,
    gov,
    tokenA,
    tokenB,
):
    gas_price(0)
    joint = gov.deploy(
        SushiJoint,
        providerA,
        providerB,
        router,
        weth,
        rewards,
        callPool_addresses[tokenA.symbol()],
        putPool_addresses[tokenA.symbol()],
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
    strategy.setHealthCheck("0xDDCea799fF1699e98EDF118e0629A974Df7DF012", {"from": gov})
    strategy.setDoHealthCheck(False, {"from": gov})
    Contract(strategy.healthCheck()).setlossLimitRatio(1000, {"from": gov})
    Contract(strategy.healthCheck()).setProfitLimitRatio(2000, {"from": gov})
    yield strategy


@pytest.fixture
def providerB(strategist, keeper, vaultB, ProviderStrategy, gov):
    strategy = strategist.deploy(ProviderStrategy, vaultB)
    strategy.setKeeper(keeper, {"from": gov})
    vaultB.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    strategy.setHealthCheck("0xDDCea799fF1699e98EDF118e0629A974Df7DF012", {"from": gov})
    strategy.setDoHealthCheck(False, {"from": gov})
    Contract(strategy.healthCheck()).setlossLimitRatio(1000, {"from": gov})
    Contract(strategy.healthCheck()).setProfitLimitRatio(2000, {"from": gov})
    yield strategy


putPool_addresses = {
    "WETH": "0x790e96E7452c3c2200bbCAA58a468256d482DD8b",
    "WBTC": "0x7A42A60F8bA4843fEeA1bD4f08450D2053cC1ab6",
}
callPool_addresses = {
    "WETH": "0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d",
    "WBTC": "0xfA77f713901a840B3DF8F2Eb093d95fAC61B215A",
}


@pytest.fixture(autouse=True)
def provideLiquidity(tokenA, tokenB, tokenA_whale, tokenB_whale, amountA, amountB):
    hegic_gov = "0xf15968a096fc8f47650001585d23bee819b5affb"
    putPool = Contract(putPool_addresses[tokenA.symbol()])
    callPool = Contract(callPool_addresses[tokenA.symbol()])

    callPool.setMaxDepositAmount(
        2 ** 256 - 1,
        2 ** 256 - 1,
        {"from": hegic_gov, "gas": 6_000_000, "gas_price": 0},
    )
    putPool.setMaxDepositAmount(
        2 ** 256 - 1,
        2 ** 256 - 1,
        {"from": hegic_gov, "gas": 6_000_000, "gas_price": 0},
    )

    tokenA.approve(
        callPool, 2 ** 256 - 1, {"from": tokenA_whale, "gas": 6_000_000, "gas_price": 0}
    )
    callPool.provideFrom(
        tokenA_whale,
        amountA,
        False,
        0,
        {"from": tokenA_whale, "gas": 6_000_000, "gas_price": 0},
    )
    tokenB.approve(
        putPool, 2 ** 256 - 1, {"from": tokenB_whale, "gas": 6_000_000, "gas_price": 0}
    )
    putPool.provideFrom(
        tokenB_whale,
        amountB,
        False,
        0,
        {"from": tokenB_whale, "gas": 6_000_000, "gas_price": 0},
    )


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


@pytest.fixture(autouse=True)
def mock_chainlink(AggregatorMock, gov):
    owner = "0x21f73d42eb58ba49ddb685dc29d3bf5c0f0373ca"

    priceProvider = Contract("0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419")
    aggregator = gov.deploy(AggregatorMock, 0)

    priceProvider.proposeAggregator(
        aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    )
    priceProvider.confirmAggregator(
        aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    )

    yield aggregator


@pytest.fixture(autouse=True)
def first_sync(mock_chainlink, joint):
    reserveA, reserveB = joint.getReserves()
    pairPrice = (
        reserveB
        / reserveA
        * 10 ** Contract(joint.tokenA()).decimals()
        / 10 ** Contract(joint.tokenB()).decimals()
        * 1e8
    )
    mock_chainlink.setPrice(pairPrice, {"from": accounts[0]})


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
