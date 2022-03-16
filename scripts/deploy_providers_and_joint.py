from brownie import Contract, SpookyJoint, accounts, config, ProviderStrategy, network

def main():

    acct = accounts.add(config["accounts"][0])
    
    # USDC
    tokenA = Contract("0x04068DA6C83AFCFA0e13ba15A6696662335D5B75")
    vaultA = Contract("0xEF0210eB96c7EB36AF8ed1c20306462764935607")
    # WFTM
    tokenB = Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83")
    vaultB = Contract("0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0")

    # Provider strats
    if network.show_active() == "ftm-main":
        provider_strat = acct.deploy(ProviderStrategy, vaultA, publish_source=True)
    else:
        provider_strat = acct.deploy(ProviderStrategy, vaultA)

    print(f"Original provider strat deployed to {provider_strat.address}")
    providerA = ProviderStrategy.at(provider_strat.clone(vaultA).return_value)
    print(f"Provider A strat deployed to {providerA.address}")
    providerB = ProviderStrategy.at(provider_strat.clone(vaultB).return_value)
    print(f"Provider B strat deployed to {providerB.address}")

    # SPooky router
    router = Contract("0xF491e7B69E4244ad4002BC14e878a34207E38c29")

    # BOO
    rewards = Contract("0x841FAD6EAe12c286d1Fd18d1d525DFfA75C7EFFE")

    # HedgilV2
    hedgilV2 = Contract("0x6E7d6Daa034fD0188f879E5648f63D821F7C0702")

    # MC
    masterchef = Contract("0x2b2929E785374c651a81A63878Ab22742656DcDd")
    mc_pid = 2

    # Deploy joint
    if network.show_active() == "ftm-main":
        joint = acct.deploy(
                SpookyJoint,
                providerA,
                providerB,
                router,
                tokenB,
                rewards,
                hedgilV2,
                masterchef,
                mc_pid, publish_source=True
            )
    else:
        joint = acct.deploy(
                SpookyJoint,
                providerA,
                providerB,
                router,
                tokenB,
                rewards,
                hedgilV2,
                masterchef,
                mc_pid
                )
    print(f"Joint deployed to {joint.address}")

    # TODOs in gov:
    # - add strat A to vault A
    # - add strat B to vault B
    # - setjoint in each provider strat

    # TODOs in sms:
    # - set healthcheck for each strat
    # - set hedgebudget for joint
    # - set hedging period