import pytest
from brownie import config, Contract


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def gov(accounts, vaultA):
    yield accounts.at(vaultA.governance(), force=True)


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
def strategist(accounts, providerA):
    yield accounts.at(providerA.strategist(), force=True)
    # yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def vaultB():
    # WOOFY vault
    yield Contract("0x6864355183462A0ECA10b5Ca90BC89BB1361d3CB")


@pytest.fixture
def vaultA():
    # YFI vault
    yield Contract("0x2C850cceD00ce2b14AA9D658b7Cad5dF659493Db")


@pytest.fixture
def tokenA(vaultA):
    yield Contract(vaultA.token())


@pytest.fixture
def tokenB(vaultB):
    yield Contract(vaultB.token())


@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0x0845c0bFe75691B1e21b24351aAc581a7FB6b7Df", force=True)


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0xfD0aB56B83130ce8f2b7A4f4d4532dEe495c0794", force=True)


@pytest.fixture
def amountA():
    yield 1 * 1e18


@pytest.fixture
def amountB(amountA):
    yield amountA


@pytest.fixture
def weth():
    yield Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")


@pytest.fixture
def router():
    yield Contract("0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52")


@pytest.fixture
def masterchef():
    yield Contract("0x9083EA3756BDE6Ee6f27a6e996806FBD37F6F093")


@pytest.fixture
def reward():
    yield Contract("0x5Cc61A78F164885776AA610fb0FE1257df78E59B")  # spirit token


@pytest.fixture
def mc_pid():
    yield 23


@pytest.fixture
def joint(
    gov, providerA, providerB, SpiritJoint, router, masterchef, reward, weth, mc_pid
):
    # joint = Contract("0x327025a6Cb4A4b61071B53066087252B779BF8B0")
    joint = gov.deploy(
        SpiritJoint, providerA, providerB, router, weth, masterchef, reward, mc_pid
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})
    providerA.setInvestWant(True, {"from": gov})
    providerB.setInvestWant(True, {"from": gov})
    providerA.setTakeProfit(False, {"from": gov})
    providerB.setTakeProfit(False, {"from": gov})

    yield joint


@pytest.fixture
def providerA():
    providerA = Contract("0xecc1DFF0C8450A5A16E56211c43182B95580f9Cf")
    yield providerA


@pytest.fixture
def providerB():
    providerB = Contract("0xaA944D01b361b25a11F185C61530937a7a9C47a6")
    yield providerB


@pytest.fixture(autouse=True)
def setDepositLimits(vaultA, vaultB, providerA, providerB, amountA, amountB, gov):
    vaultA.setDepositLimit(vaultA.depositLimit() + amountA, {"from": gov})
    vaultB.setDepositLimit(vaultB.depositLimit() + amountB, {"from": gov})
    vaultA.updateStrategyDebtRatio(providerA, 10000, {"from": gov})
    vaultB.updateStrategyDebtRatio(providerB, 10000, {"from": gov})
    vaultA.updateStrategyMaxDebtPerHarvest(providerA, amountA, {"from": gov})
    vaultB.updateStrategyMaxDebtPerHarvest(providerB, amountB, {"from": gov})
