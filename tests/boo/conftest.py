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
def attacker(accounts):
    yield accounts[6]


@pytest.fixture
def vaultB():
    # BOO vault
    yield Contract("0x79330397e161C67703e9bce2cA2Db73937D5fc7e")


@pytest.fixture
def vaultA():
    # WFTM vault
    yield Contract("0x36e7aF39b921235c4b01508BE38F27A535851a5c")


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0xACACa07e398d4946AD12232F40f255230e73Ca72", force=True)


@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0xBB634cafEf389cDD03bB276c82738726079FcF2E", force=True)


@pytest.fixture
def tokenA_amount():
    yield 150_000 * 1e18


@pytest.fixture
def tokenB_amount():
    yield 10_000 * 1e18


@pytest.fixture
def weth():
    yield Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")


@pytest.fixture
def router():
    yield Contract("0xF491e7B69E4244ad4002BC14e878a34207E38c29")


@pytest.fixture
def masterchef():
    yield Contract("0x2b2929E785374c651a81A63878Ab22742656DcDd")


@pytest.fixture
def boo():
    yield Contract("0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE")


@pytest.fixture
def mc_pid():
    yield 0


@pytest.fixture
def joint(gov, providerA, providerB, BooJoint, router, masterchef, boo, weth, mc_pid):
    # joint = Contract("0x327025a6Cb4A4b61071B53066087252B779BF8B0")
    joint = gov.deploy(
        BooJoint, providerA, providerB, router, weth, masterchef, boo, mc_pid
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(gov, strategist, keeper, vaultA, ProviderStrategy):
    # strategy = Contract("0x51DaA92f3E1F6F39924aF796c9f63c1d35A52386")
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper, {"from": gov})
    strategy.setStrategist(strategist, {"from": gov})

    # free up some debt ratio space
    vaultA.revokeStrategy("0x8F43b5CeD3e892dBb3951694D80cB6E4313F2F58", {"from": gov})
    vaultA.addStrategy(
        strategy, 10000 - vaultA.debtRatio(), 0, 2 ** 256 - 1, 1_000, {"from": gov}
    )

    yield strategy


@pytest.fixture
def providerB(gov, strategist, keeper, vaultB, ProviderStrategy):
    # strategy = Contract("0x61b7e35Ec9EA46DbdC0F7A85355F1025048C3E60")
    strategy = strategist.deploy(ProviderStrategy, vaultB)
    strategy.setKeeper(keeper, {"from": gov})
    strategy.setStrategist(strategist, {"from": gov})

    # free up some debt ratio space
    vaultB.revokeStrategy("0xf8c08cE855D1ABA492202ecf47eaa3d2a7DE2eC5", {"from": gov})
    vaultB.addStrategy(
        strategy, 10000 - vaultB.debtRatio(), 0, 2 ** 256 - 1, 1_000, {"from": gov}
    )

    yield strategy
