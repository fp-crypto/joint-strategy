import pytest

from brownie import accounts, chain, config, Contract, web3, Wei, \
    SpookyJoint, SolidexJoint, SpiritJoint, SushiJoint
from brownie.network import gas_price, gas_limit
import requests

# Function scoped isolation fixture to enable xdist.
# Snapshots the chain before each test and reverts after test completion.
# @pytest.fixture(scope="function", autouse=True)
# def shared_setup(fn_isolation):
#     pass

@pytest.fixture(scope="session", autouse=False)
def tenderly_fork(web3):
    gas_price(1)
    fork_base_url = "https://simulate.yearn.network/fork"
    payload = {"network_id": "250"}
    resp = requests.post(fork_base_url, headers={}, json=payload)
    fork_id = resp.json()["simulation_fork"]["id"]
    fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
    print(fork_rpc_url)
    tenderly_provider = web3.HTTPProvider(fork_rpc_url, {"timeout": 600})
    web3.provider = tenderly_provider
    print(f"https://dashboard.tenderly.co/yearn/yearn-web/fork/{fork_id}")

@pytest.fixture(scope="session", autouse=True)
def donate(wftm, accounts, gov, tokenA_whale, tokenB_whale):
    donor = accounts.at(wftm, force=True)
    for i in range(10):
        donor.transfer(accounts[i], 100e18)
    donor.transfer(gov, 100e18)
    
@pytest.fixture(scope="session", autouse=True)
def reset_chain(chain):
    print(f"Initial Height: {chain.height}")
    yield
    print(f"\nEnd Height: {chain.height}")
    print(f"Reset chain")
    chain.reset()
    print(f"Reset Height: {chain.height}")

######### ACCOUNTS & CONTRACTS
    
@pytest.fixture(scope="session")
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture(scope="session")
def strat_ms(accounts):
    yield accounts.at("0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7", force=True)


@pytest.fixture(scope="session")
def user(accounts):
    yield accounts[0]


@pytest.fixture(scope="session")
def stable():
    yield True


@pytest.fixture(scope="session")
def rewards(accounts):
    yield accounts[1]


@pytest.fixture(scope="session")
def guardian(accounts):
    yield accounts[2]


@pytest.fixture(scope="session")
def management(accounts):
    yield accounts[3]


@pytest.fixture(scope="session")
def strategist(accounts):
    yield accounts[4]


@pytest.fixture(scope="session")
def keeper(accounts):
    yield accounts[5]


@pytest.fixture(scope="session")
def hedgilV2():
    yield Contract("0x6E7d6Daa034fD0188f879E5648f63D821F7C0702")


@pytest.fixture(scope="session")
def chainlink_owner():
    yield accounts.at("0x9ba4c51512752E79317b59AB4577658e12a43f55", force=True)


@pytest.fixture(scope="session")
def deployer(accounts):
    yield accounts.at("0xcc4c922db2ef8c911f37e73c03b632dd1585ad0e", force=True)


@pytest.fixture(scope="session")
def dai():
    yield Contract(token_addresses["DAI"])


@pytest.fixture(scope="session")
def weth():
    token_address = "0x74b23882a30290451A17c44f4F05243b6b58C76d"
    yield Contract(token_address)


@pytest.fixture(scope="session")
def wftm():
    token_address = token_addresses["WFTM"]
    yield Contract(token_address)


@pytest.fixture(scope="session")
def usdc():
    token_address = token_addresses["USDC"]
    yield Contract(token_address)


@pytest.fixture(scope="session")
def mim():
    token_address = token_addresses["MIM"]
    yield Contract(token_address)

@pytest.fixture(scope="session")
def registry():
    yield Contract("")


@pytest.fixture(scope="session")
def live_vaultA(registry, tokenA):
    yield registry.latestVault(tokenA)


@pytest.fixture(scope="session")
def live_vaultB(registry, tokenB):
    yield registry.latestVault(tokenB)

######### PARAMETERS

# Select the type of hedge to use for the joint
@pytest.fixture(
    params=[
        # "nohedge",
        "hedgilV2",
        # "hegic"
    ],
    scope="session",
    autouse=True,)
def hedge_type(request):
    yield request.param

@pytest.fixture(
    params=[
        # "SUSHI",
        # "SOLID",
        # "SPIRIT",
        # "UNI",
        "SPOOKY"
    ],
    scope="session",
    autouse=True,)
def dex(request):
    yield request.param

# TODO: uncomment those tokens you want to test as want
@pytest.fixture(
    params=[
        # 'WBTC', # WBTC
        # "YFI",  # YFI
        "ETH",  # WETH
        # 'LINK', # LINK
        'fUSDT', # USDT
        'DAI', # DAI
        # "WFTM",
        "USDC",  # USDC
        # "WFTM",
        # "BOO",
        "BTC",
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
        "WFTM",
        # "MIM",
        # "FRAX",
    ],
    scope="session",
    autouse=True,
)
def tokenB(request):
    yield Contract(token_addresses[request.param])

@pytest.fixture(params=[
    # "SEX",
    "BOO"
    ], scope="session", autouse=True)
def rewards(request):
    rewards_address = token_addresses[request.param]  # sushi
    yield Contract(rewards_address)

joint_type = {
    "SPOOKY": {
        "nohedge": "",
        "hedgilV2": SpookyJoint
    },
    "SOLID": {
        "nohedge": SolidexJoint,
        "hedgilV2": ""
    },
    "SUSHI": {
        "nohedge": "",
        "hedgilV2": "",
        "hegic": SushiJoint
    },
    "SPIRIT": {
        "nohedge": "",
        "hedgilV2": ""
    }
}
@pytest.fixture()
def joint_to_use(dex, hedge_type):
    yield joint_type[dex][hedge_type]

token_addresses = {
    "YFI": "0x29b0Da86e484E1C0029B56e817912d778aC0EC69",  # YFI
    "ETH": "0x74b23882a30290451A17c44f4F05243b6b58C76d",  # WETH
    "DAI": "0x8D11eC38a3EB5E956B052f67Da8Bdc9bef8Abf3E",  # DAI
    "USDC": "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75",  # USDC
    "SUSHI": "0x6B3595068778DD592e39A122f4f5a5cF09C90fE2",  # SUSHI
    "MIM": "0x82f0b8b456c1a451378467398982d4834b6829c1",  # MIM
    "WFTM": "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83",  # WFTM
    "SPIRIT": "0x5Cc61A78F164885776AA610fb0FE1257df78E59B",  # SPIRIT
    "BOO": "0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE",  # BOO
    "SEX": "0xD31Fcd1f7Ba190dBc75354046F6024A9b86014d7",  # SEX
    "SOLID": "0x888EF71766ca594DED1F0FA3AE64eD2941740A20",  # SOLID
    "FRAX": "0xdc301622e621166BD8E82f2cA0A26c13Ad0BE355", #FRAX
    "BTC": "0x321162Cd933E2Be498Cd2267a90534A804051b11", #BTC
    "fUSDT": "0x049d68029688eAbF473097a2fC38ef61633A3C7A", #fUSDT
}

whale_addresses = {
    "SOLID": "0x1d1A1871d1830D4b5087212c820E5f1252379c2c",
    "SEX": "0x1434f19804789e494E271F9CeF8450e51790fcD2",
    "YFI": "0x29b0Da86e484E1C0029B56e817912d778aC0EC69",
    "ETH": "0x25c130B2624CF12A4Ea30143eF50c5D68cEFA22f",
    "USDC": "0xbcab7d083Cf6a01e0DdA9ed7F8a02b47d125e682",
    "DAI": "0x27E611FD27b276ACbd5Ffd632E5eAEBEC9761E40",
    "SUSHI": "0xae75A438b2E0cB8Bb01Ec1E1e376De11D44477CC",
    "WFTM": "0x5AA53f03197E08C4851CAD8C92c7922DA5857E5d",
    "MIM": "0x2dd7C9371965472E5A5fD28fbE165007c61439E1",
    "BOO": "0x0D0707963952f2fBA59dD06f2b425ace40b492Fe",
    "FRAX": "0x7a656B342E14F745e2B164890E88017e27AE7320",
    "BTC": "0x38aCa5484B8603373Acc6961Ecd57a6a594510A3",
    "fUSDT": "0x2823D10DA533d9Ee873FEd7B16f4A962B2B7f181",
}

lp_whales = {
    "SPOOKY": 
        {
            "WFTM": {
                "USDC": "0x7495f066Bb8a0f71908DeB8d4EFe39556f13f58A",
                "BOO": "0xc94A3Ff0bac12eeB9ff0CC4e08511E1FFaD6ba94",
                "DAI": "0x7495f066Bb8a0f71908DeB8d4EFe39556f13f58A",
                "BTC": "0xb78E3E8bd36B3228322d0a9d3271B5FbB7997fA3",
                "ETH": "0x5a87E9A0A765fE5A69fA6492D3C7838DC1511805",
                "fUSDT": "0x10890742A1a20A936132072C20Ae77b081486190",
                }
        },
    "SOLID": 
        {
            "USDC": {
                "MIM": "0xC009BC33201A85800b3593A40a178521a8e60a02",
                "FRAX": "0x6340dd65D9da8E39651229C1ba9F0ee069E7E4f8",
                "DAI": "0x9C7EaC4b4a8d37fA9dE7e4cb81F0a99256C672d1",
                }
        },
}


@pytest.fixture(scope="session", autouse=True)
def lp_whale(dex, tokenA, tokenB):
    yield lp_whales[dex][tokenB.symbol()][tokenA.symbol()]


@pytest.fixture(scope="session", autouse=True)
def tokenA_whale(tokenA):
    yield whale_addresses[tokenA.symbol()]


@pytest.fixture(scope="session", autouse=True)
def tokenB_whale(tokenB):
    yield whale_addresses[tokenB.symbol()]

mc_pids = {
    "WFTM": {
        "MIM": 24,
        "USDC": 2,
        "BOO": 0,
        "DAI": 3,
        "BTC": 4,
        "ETH": 5,
        "fUSDT": 1,
    }
}

@pytest.fixture
def mc_pid(tokenA, tokenB):
    if tokenB.symbol() in mc_pids.keys():
        yield mc_pids[tokenB.symbol()][tokenA.symbol()]
    else:
        yield ""

router_addresses = {
    "UNI": "",
    "SUSHI": "",
    "SPOOKY": "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
    "SOLID": "0xa38cd27185a464914D3046f0AB9d43356B34829D",
    "SPIRIT": "0x16327E3FbDaCA3bcF7E38F5Af2599D2DDc33aE52",
}

@pytest.fixture
def router(dex):
    yield Contract(router_addresses[dex])

lp_depositor_addresses = {
    "SOLID": "0x26E1A0d851CF28E697870e1b7F053B605C8b060F",
}

@pytest.fixture(scope="session")
def lp_depositor(dex):
    if dex in lp_depositor_addresses.keys():
        yield Contract(lp_depositor_addresses[dex])
    else: 
        yield ""

# Non-comprehensive, find the full list here to add your own: https://docs.chain.link/docs/fantom-price-feeds/
oracle_addresses = {
    "WFTM": "0xf4766552D15AE4d256Ad41B6cf2933482B0680dc",
    "USDC": "0x2553f4eeb82d5A26427b8d1106C51499CBa5D99c",
    "MIM": "0x28de48D3291F31F839274B8d82691c77DF1c5ceD",
    "FRAX": "0xBaC409D670d996Ef852056f6d45eCA41A8D57FbD",
    "DAI": "0x91d5DEFAFfE2854C7D02F50c80FA1fdc8A721e52",
    "BTC": "0x8e94C22142F4A64b99022ccDd994f4e9EC86E4B4",
    "ETH": "0x11DdD3d147E5b83D01cee7070027092397d63658",
    "fUSDT": "0xF64b636c5dFe1d3555A847341cDC449f612307d0",
}


@pytest.fixture(scope="session")
def tokenA_oracle(tokenA):
    yield Contract(oracle_addresses[tokenA.symbol()])


@pytest.fixture(scope="session")
def tokenB_oracle(tokenB):
    yield Contract(oracle_addresses[tokenB.symbol()])

@pytest.fixture
def rewards_whale(rewards):
    yield whale_addresses[rewards.symbol()]

masterchef_addresses = {
    "SUSHI": "0xc2EdaD668740f1aA35E4D8f227fB8E17dcA888Cd",
    "SPIRIT": "0x9083EA3756BDE6Ee6f27a6e996806FBD37F6F093",
    "BOO": "0x2b2929E785374c651a81A63878Ab22742656DcDd",
    "SOLID": "0x2b2929E785374c651a81A63878Ab22742656DcDd",
    "SEX": "0x2b2929E785374c651a81A63878Ab22742656DcDd",
}

@pytest.fixture
def masterchef(rewards):
    yield Contract(masterchef_addresses[rewards.symbol()])

hedgil_pools = {
    "WFTM": {
        "MIM": "0x150C42e9CB21354030967579702e0f010e208E86",
        "USDC": "0x8C2cC5ff69Bc3760d7Ce81812A2848421495972A",
    }
}

######### UTILITIES

token_prices = {
    "WBTC": 60_000,
    "BTC": 38_000,
    "ETH": 4_500,
    "LINK": 20,
    "YFI": 30_000,
    "USDT": 1,
    "fUSDT": 1,
    "USDC": 1,
    "DAI": 1,
    "WFTM": 3,
    "MIM": 1,
    "FRAX": 1,
    "BOO": 11,
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
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount

######### DEPLOYMENTS

@pytest.fixture(scope="function", autouse=True)
def vaultA(pm, gov, rewards, guardian, management, tokenA):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenA, gov, rewards, "", "", guardian, management, {"from": gov, "gas_price":0})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov, "gas_price":0})
    vault.setManagement(management, {"from": gov, "gas_price":0})
    yield vault


@pytest.fixture(scope="function", autouse=True)
def vaultB(pm, gov, rewards, guardian, management, tokenB):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(tokenB, gov, rewards, "", "", guardian, management, {"from": gov, "gas_price":0})
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov, "gas_price":0})
    vault.setManagement(management, {"from": gov, "gas_price":0})
    yield vault

@pytest.fixture
def joint(
    providerA,
    providerB,
    joint_to_use,
    masterchef,
    rewards,
    router,
    wftm,
    mc_pid,
    hedgilV2,
    gov,
    lp_depositor,
    stable
):
    
    if (joint_to_use == SpookyJoint): 
        joint = gov.deploy(
            joint_to_use,
            providerA,
            providerB,
            router,
            wftm,
            rewards,
            hedgilV2,
            masterchef,
            mc_pid,
        )
    elif (joint_to_use == SolidexJoint):
        joint = gov.deploy(
            joint_to_use,
            providerA,
            providerB,
            router,
            wftm,
            rewards,
            lp_depositor,
            stable
        )
    
    joint.setMaxPercentageLoss(500, {"from": gov})
    joint.setHedgeBudget(25)
    joint.setHedgingPeriod(2 * 86400)

    providerA.setJoint(joint, {"from": gov})
    providerB.setJoint(joint, {"from": gov})

    yield joint


@pytest.fixture
def providerA(strategist, keeper, vaultA, ProviderStrategy, gov):
    strategy = strategist.deploy(ProviderStrategy, vaultA)
    strategy.setKeeper(keeper, {"from": gov, "gas_price":0})
    vaultA.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov, "gas_price":0})
    strategy.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov, "gas_price":0})
    strategy.setDoHealthCheck(False, {"from": gov, "gas_price":0})
    Contract(strategy.healthCheck()).setlossLimitRatio(
        1000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16", "gas_price":0}
    )
    Contract(strategy.healthCheck()).setProfitLimitRatio(
        2000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16", "gas_price":0}
    )
    yield strategy


@pytest.fixture
def providerB(strategist, keeper, vaultB, ProviderStrategy, gov):
    strategy = strategist.deploy(ProviderStrategy, vaultB)
    strategy.setKeeper(keeper, {"from": gov, "gas_price":0})
    vaultB.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov, "gas_price":0})
    strategy.setHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0", {"from": gov, "gas_price":0})
    strategy.setDoHealthCheck(False, {"from": gov, "gas_price":0})
    Contract(strategy.healthCheck()).setlossLimitRatio(
        1000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16", "gas_price":0}
    )
    Contract(strategy.healthCheck()).setProfitLimitRatio(
        2000, {"from": "0x72a34AbafAB09b15E7191822A679f28E067C4a16", "gas_price":0}
    )
    yield strategy

@pytest.fixture(autouse=True)
def provideLiquidity(
    hedgilV2, tokenB, tokenB_whale, hedge_type
):
    if hedge_type == "hedgilV2":
        tokenB.approve(hedgilV2, 2 ** 256 - 1, {"from": tokenB_whale, "gas_price": "0"})
        hedgilV2.provideLiquidity(
            100_000 * 10 ** tokenB.decimals(),
            0,
            tokenB_whale,
            {"from": tokenB_whale, "gas_price": "0"},
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


@pytest.fixture(scope="session", autouse=False)
def LPHedgingLibrary(LPHedgingLib, gov):

    yield gov.deploy(LPHedgingLib)


@pytest.fixture(scope="session", autouse=True)
def RELATIVE_APPROX():
    yield 1e-5


@pytest.fixture(autouse=False)
def mock_chainlink(AggregatorMock, gov):
    # owner = "0x21f73d42eb58ba49ddb685dc29d3bf5c0f0373ca"

    # priceProvider = Contract("0x5f4ec3df9cbd43714fe2740f5e3616155c5b8419")
    # aggregator = gov.deploy(AggregatorMock, 0)

    # priceProvider.proposeAggregator(
    #    aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    # )
    # priceProvider.confirmAggregator(
    #    aggregator.address, {"from": owner, "gas": 6_000_000, "gas_price": 0}
    # )

    # yield aggregator
    return


@pytest.fixture(autouse=False)
def first_sync(joint):
    relayer = "0x33E0E07cA86c869adE3fc9DE9126f6C73DAD105e"
    imp = Contract("0x5bfab94edE2f4d911A6CC6d06fdF2d43aD3c7068")
    lp_token = Contract(joint.pair())
    (reserve0, reserve1, _) = lp_token.getReserves()
    ftm_price = reserve0 / reserve1 * 10 ** (9 + 12)
    print(f"Current price is: {ftm_price/1e9}")
    imp.relay(["FTM"], [ftm_price], [chain.time()], [4281375], {"from": relayer})


@pytest.fixture(autouse=False)
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


@pytest.fixture(autouse=True)
def trade_factory(joint, yMechs_multisig):
    tf = Contract(joint.tradeFactory())
    tf.grantRole(tf.STRATEGY(), joint, {"from": yMechs_multisig, "gas_price": 0})
    yield tf


@pytest.fixture(scope="session")
def yMechs_multisig():
    yield accounts.at("0x9f2A061d6fEF20ad3A656e23fd9C814b75fd5803", force=True)

    
@pytest.fixture(scope="function", autouse=True)
def auth_yswaps(joint, trade_factory, yMechs_multisig):
    gas_price(0)
    trade_factory.grantRole(
        trade_factory.STRATEGY(), joint, {"from": yMechs_multisig, "gas_price": 0}
    )

@pytest.fixture(autouse=True)
def trade_factory(joint, yMechs_multisig):
    tf = Contract(joint.tradeFactory())
    tf.grantRole(
        tf.STRATEGY(), joint, {"from": yMechs_multisig, "gas_price": 0}
    )
    yield tf
