from brownie import Contract

def main():

    # BOO - WFTM
    lp_token_to_find = "0xe120ffBDA0d14f3Bb6d6053E90E63c572A66a428"

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
    
