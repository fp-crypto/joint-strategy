from brownie import Contract

def main():

    # BOO - WFTM
    lp_token_to_find = "0x5965E53aa80a0bcF1CD6dbDd72e6A9b2AA047410"

    # SPOOKY
    masterchef = Contract("0x2b2929E785374c651a81A63878Ab22742656DcDd")

    i = 0
    res = ""
    while (i < 1e6):
        print(f"Trying with i = {i}")
        res = masterchef.poolInfo(i)["lpToken"]
        if res == lp_token_to_find:
            break
        else:
            i += 1
    
    print(f"Success with i = {i}, lp_token {lp_token_to_find} found")
    
