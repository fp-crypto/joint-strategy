from brownie import Contract, accounts, interface, BooJoint
import click
def deploy():
    deployer = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    wftm = Contract("0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", owner=deployer)
    vault_wftm = Contract("0x0DEC85e74A92c52b7F708c4B10207D9560CEFaf0", owner=deployer)
    usdc = Contract("0x04068DA6C83AFCFA0e13ba15A6696662335D5B75", owner=deployer)
    vault_usdc = Contract("0x3935486EE039B476241DA653baf06A8fc366e67F", owner=deployer)
    masterchef =Contract("0x2b2929E785374c651a81A63878Ab22742656DcDd", owner=deployer)
    router = Contract("0xF491e7B69E4244ad4002BC14e878a34207E38c29", owner=deployer)
    reward = Contract("0x841fad6eae12c286d1fd18d1d525dffa75c7effe", owner=deployer)
    providerB = Contract("0x43F0CA5d5fab896AaA748053Fe8D4aa661A74B6f", owner=deployer)
    providerA = Contract("0xb51a8a88a3ed9e5043e710BFfC8EaD680395566b", owner=deployer)
    hedgil = Contract("0x2E81D4acd71b42ee771cab0836A92a3e3799ddFD", owner=deployer)
    pid = 2

    joint_deployed = deployer.deploy(
        BooJoint,
        providerA,
        providerB,
        router,
        wftm,
        masterchef,
        reward,
        pid,
        hedgil, 
        publish_source=True
    )

    print(f"Deployed BooJoint at {joint_deployed}")
