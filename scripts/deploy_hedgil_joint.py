from brownie import Contract, accounts, interface, BooJoint
import click
def deploy_BooJoint():
    deployer = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    tokenA = Contract("", owner=deployer)
    vaultA = Contract("", owner=deployer)
    tokenB = Contract("", owner=deployer)
    vaultB = Contract("", owner=deployer)
    wftm = Contract("", owner=deployer)
    masterchef =Contract("", owner=deployer)
    pid = 0
    router = Contract("", owner=deployer)
    reward = Contract("", owner=deployer)
    providerA = Contract("", owner=deployer)
    providerB = Contract("", owner=deployer)
    hedgil = Contract("", owner=deployer)

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

    print(f"Deployed {joint_deployed.name()} at {joint_deployed}")

def deploy_SushiJoint():
    deployer = accounts.load(click.prompt("Account", type=click.Choice(accounts.load())))
    tokenA = Contract("", owner=deployer)
    vaultA = Contract("", owner=deployer)
    tokenB = Contract("", owner=deployer)
    vaultB = Contract("", owner=deployer)
    wftm = Contract("", owner=deployer)
    masterchef =Contract("", owner=deployer)
    pid = 0
    router = Contract("", owner=deployer)
    reward = Contract("", owner=deployer)
    providerA = Contract("", owner=deployer)
    providerB = Contract("", owner=deployer)
    hedgil = Contract("", owner=deployer)

    joint_deployed = deployer.deploy(
        SushiJoint,
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

    print(f"Deployed {joint_deployed.name()} at {joint_deployed}")
