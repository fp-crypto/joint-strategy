import pytest
from brownie import config, Contract, interface


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def gov(accounts):
    yield accounts.at("0x72a34AbafAB09b15E7191822A679f28E067C4a16", force=True)


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
def band_oracle():
    yield interface.IStdReference("0x56E2898E0ceFF0D1222827759B56B28Ad812f92F")

@pytest.fixture
def tokenA():
    # WFTM
    yield interface.IERC20Extended("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")


@pytest.fixture
def tokenB():
    # USDC
    yield interface.IERC20Extended("0x04068DA6C83AFCFA0e13ba15A6696662335D5B75")

# @pytest.fixture
# def registry():
#     a = Contract.from_explorer("0x58ECFA9cFffC09E2e5e1fc75606cb46c00c923Da")
#     yield Contract.from_abi("registry", "0x41679043846d1B16b44FBf6E7FE531390e5bf092", a.abi)

@pytest.fixture
def vaultA(pm, gov, rewards, guardian, management, tokenA):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenA, gov, rewards, "", "", guardian, management, {"from": gov})

    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    yield vault

@pytest.fixture
def vaultB(pm, gov, rewards, guardian, management, tokenB):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenB, gov, rewards, "", "", guardian, management, {"from": gov})

    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagementFee(0, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    yield vault

@pytest.fixture
def tokenA_whale(accounts):
    yield accounts.at("0xF5BCE5077908a1b7370B9ae04AdC565EBd643966", force=True)


@pytest.fixture
def tokenB_whale(accounts):
    yield accounts.at("0x3F27AAa1f1918f6f8BfEb55fF5A3148ba2e24143", force=True)


@pytest.fixture
def sushi_whale(accounts):## BOO
    yield accounts.at("0x841fad6eae12c286d1fd18d1d525dffa75c7effe", force=True)


@pytest.fixture
def amountA(tokenA):
    yield 7000 * 10 ** tokenA.decimals()


@pytest.fixture
def amountB(tokenB, joint):
    reserve0, reserve1, a = interface.IUniswapV2Pair(joint.pair()).getReserves()
    yield int(7000 * reserve0/reserve1 * 1e12 * 10 ** tokenB.decimals())  # price A/B times amountA


@pytest.fixture
def weth():
    yield interface.IERC20("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")


@pytest.fixture
def router():
    # Sushi
    yield interface.IUniswapV2Router01("0xF491e7B69E4244ad4002BC14e878a34207E38c29")


@pytest.fixture
def masterchef():
    yield interface.IMasterchef("0x2b2929E785374c651a81A63878Ab22742656DcDd")


@pytest.fixture
def boo():
    yield interface.IERC20("0x841fad6eae12c286d1fd18d1d525dffa75c7effe")


@pytest.fixture
def mc_pid():
    yield 2

@pytest.fixture
def hedgil():
    yield interface.IHedgilV1("0xe21aDE67381D17F7c049C04494CE11667a92EEF5")


@pytest.fixture
def joint(
    gov, providerA, providerB, BooJoint, router, masterchef, boo, weth, mc_pid, hedgil
):
    joint = gov.deploy(
        BooJoint, providerA, providerB, router, weth, masterchef, boo, mc_pid, hedgil
    )

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(gov, strategist, keeper, vaultA, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper)

    vaultA.addStrategy(strategy, 10000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy


@pytest.fixture
def providerB(gov, strategist, vaultB, ProviderStrategy):
    strategy = strategist.deploy(ProviderStrategy, vaultB)

    vaultB.addStrategy(strategy, 10000, 0, 2 ** 256 - 1, 1_000, {"from": gov})

    yield strategy
