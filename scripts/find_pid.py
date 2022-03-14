from brownie import Contract

def main():

    # BOO - WFTM
    lp_token_to_find = "0xFdb9Ab8B9513Ad9E419Cf19530feE49d412C3Ee3"

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
    
