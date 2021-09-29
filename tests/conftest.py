import pytest
from brownie import config, Contract


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


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
def attacker(accounts):
    yield accounts[6]


@pytest.fixture
def tokenA():
    yield Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")  # WETH
    # yield Contract(vaultA.token())


@pytest.fixture
def tokenB():
    yield Contract("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")  # USDC
    # yield Contract(vaultB.token())


@pytest.fixture
def vaultA_test(pm, gov, rewards, guardian, management, tokenA):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenA, gov, rewards, "", "", guardian, management, {"from": gov})

    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    yield vault


@pytest.fixture
def vaultB_test(pm, gov, rewards, guardian, management, tokenB):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenB, gov, rewards, "", "", guardian, management, {"from": gov})

    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    yield vault


@pytest.fixture
def vaultA(vaultA_test, tokenA):
    yield vaultA_test
    # WETH vault (PROD)
    # vaultA_prod = Contract("0xa258C4606Ca8206D8aA700cE2143D7db854D168c")
    # assert vaultA_prod.token() == tokenA.address
    # yield vaultA_prod


@pytest.fixture
def vaultB(vaultB_test, tokenB):
    yield vaultB_test
    # YFI vault (PROD)
    # vaultB_prod = Contract("0xE14d13d8B3b85aF791b2AADD661cDBd5E6097Db1")
    # assert vaultB_prod.token() == tokenB.address
    # yield vaultB_prod


@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0x2F0b23f53734252Bda2277357e97e1517d6B042A", force=True)


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0x0A59649758aa4d66E25f08Dd01271e891fe52199", force=True)  # usdc


@pytest.fixture
def sushi_whale(accounts):
    yield accounts.at("0x8798249c2E607446EfB7Ad49eC89dD1865Ff4272", force=True)


@pytest.fixture
def amountA(tokenA):
    yield 10 * 10 ** tokenA.decimals()


@pytest.fixture
def amountB(tokenB, joint):
    reserve0, reserve1, a = Contract(joint.pair()).getReserves()
    yield reserve0 / reserve1 * 1e12 * 10 * 10 ** tokenB.decimals()  # price A/B times amountA


@pytest.fixture
def weth():
    yield Contract("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


@pytest.fixture
def router():
    # Sushi
    yield Contract("0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F")


@pytest.fixture
def masterchef():
    yield Contract("0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd")


@pytest.fixture
def sushi():
    yield Contract("0x6B3595068778DD592e39A122f4f5a5cF09C90fE2")


@pytest.fixture
def mc_pid():
    yield 1


@pytest.fixture
def LPHedgingLibrary(LPHedgingLib, gov):
    yield gov.deploy(LPHedgingLib)


@pytest.fixture
def oracle():
    yield Contract(
        Contract("0xb9ed94c6d594b2517c4296e24A8c517FF133fb6d").priceProvider()
    )


@pytest.fixture(autouse=True)
def mock_chainlink(AggregatorMock, gov):
    owner = "0x21f73d42eb58ba49ddb685dc29d3bf5c0f0373ca"

    priceProvider = Contract("0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419")
    aggregator = gov.deploy(AggregatorMock, 0)

    priceProvider.proposeAggregator(aggregator.address, {"from": owner})
    priceProvider.confirmAggregator(aggregator.address, {"from": owner})

    yield aggregator


@pytest.fixture
def joint(
    gov,
    providerA,
    providerB,
    SushiJoint,
    router,
    masterchef,
    sushi,
    weth,
    mc_pid,
    LPHedgingLibrary,
):
    joint = gov.deploy(
        SushiJoint, providerA, providerB, router, weth, sushi, masterchef, mc_pid
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(gov, strategist, keeper, vaultA, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper)

    vaultA.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy


@pytest.fixture
def providerB(gov, strategist, vaultB, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultB)

    vaultB.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy
