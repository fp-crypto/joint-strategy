// SPDX-License-Identifier: AGPL-3.0
pragma solidity 0.8.12;
pragma experimental ABIEncoderV2;

import {Address} from "@openzeppelin/contracts/utils/Address.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

import "../interfaces/IERC20Extended.sol";

import "./ySwapper.sol";

import {VaultAPI} from "@yearnvaults/contracts/BaseStrategy.sol";

interface ProviderStrategy {
    function vault() external view returns (VaultAPI);

    function strategist() external view returns (address);

    function keeper() external view returns (address);

    function want() external view returns (address);

    function totalDebt() external view returns (uint256);
}

abstract contract Joint {
    using SafeERC20 for IERC20;
    using Address for address;
    // Constant to use in ratio calculations
    uint256 internal constant RATIO_PRECISION = 1e18;
    // Provider strategy of tokenA
    ProviderStrategy public providerA;
    // Provider strategy of tokenB
    ProviderStrategy public providerB;

    // Address of tokenA
    address public tokenA;
    // Address of tokenB
    address public tokenB;

    // Reference token to use in swaps: WETH, WFTM...
    address public referenceToken;
    // Array containing reward tokens
    address[] public rewardTokens;

    // Address of the pool to LP
    address public pool;

    // Amounts that actually go into the LP position
    uint256 public investedA;
    uint256 public investedB;

    // Boolean values protecting against re-investing into the pool
    bool public dontInvestWant;
    bool public autoProtectionDisabled;

    // Thresholds to operate the strat
    uint256 public minAmountToSell;
    uint256 public maxPercentageLoss;
    uint256 public minRewardToHarvest;

    // Modifiers needed for access control normally inherited from BaseStrategy 
    modifier onlyGovernance() {
        checkGovernance();
        _;
    }

    modifier onlyVaultManagers() {
        checkVaultManagers();
        _;
    }

    modifier onlyProviders() {
        checkProvider();
        _;
    }

    modifier onlyKeepers() {
        checkKeepers();
        _;
    }

    function checkKeepers() internal {
        require(isKeeper() || isGovernance() || isVaultManager());
    }

    function checkGovernance() internal {
        require(isGovernance());
    }

    function checkVaultManagers() internal {
        require(isGovernance() || isVaultManager());
    }

    function checkProvider() internal {
        require(isProvider());
    }

    function isGovernance() internal view returns (bool) {
        return
            msg.sender == providerA.vault().governance() ||
            msg.sender == providerB.vault().governance();
    }

    function isVaultManager() internal view returns (bool) {
        return
            msg.sender == providerA.vault().management() ||
            msg.sender == providerB.vault().management();
    }

    function isKeeper() internal view returns (bool) {
        return
            (msg.sender == providerA.keeper()) ||
            (msg.sender == providerB.keeper());
    }

    function isProvider() internal view returns (bool) {
        return
            msg.sender == address(providerA) ||
            msg.sender == address(providerB);
    }

    /*
     * @notice
     *  Constructor, only called during original deploy
     * @param _providerA, provider strategy of tokenA
     * @param _providerB, provider strategy of tokenB
     * @param _referenceToken, token to use as reference, for pricing oracles and paying hedging costs (if any)
     * @param _pool, Pool to LP
     */
    constructor(
        address _providerA,
        address _providerB,
        address _referenceToken,
        address _pool
    ) {
        _initialize(_providerA, _providerB, _referenceToken, _pool);
    }

    /*
     * @notice
     *  Constructor equivalent for clones, initializing the joint and the specifics of UniV3Joint
     * @param _providerA, provider strategy of tokenA
     * @param _providerB, provider strategy of tokenB
     * @param _referenceToken, token to use as reference, for pricing oracles and paying hedging costs (if any)
     * @param _pool, Pool to LP
     */
    function _initialize(
        address _providerA,
        address _providerB,
        address _referenceToken,
        address _pool
    ) internal virtual {
        require(address(providerA) == address(0), "Joint already initialized");
        providerA = ProviderStrategy(_providerA);
        providerB = ProviderStrategy(_providerB);
        referenceToken = _referenceToken;
        pool = _pool;

        // NOTE: we let some loss to avoid getting locked in the position if something goes slightly wrong
        maxPercentageLoss = RATIO_PRECISION / 1_000; // 0.10%

        tokenA = address(providerA.want());
        tokenB = address(providerB.want());
        require(tokenA != tokenB, "!same-want");
    }

    function name() external view virtual returns (string memory);

    function shouldEndEpoch() external view virtual returns (bool);

    function _autoProtect() internal view virtual returns (bool);

    /*
     * @notice
     *  Check wether a token address is part of rewards or not
     * @param token, token address to check
     * @return wether the provided token address is a reward for the strar or not
     */
    function _isReward(address token) internal view returns (bool) {
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            if (rewardTokens[i] == token) {
                return true;
            }
        }

        return false;
    }

    /*
     * @notice
     *  Function used in harvestTrigger in providers to decide wether an epoch can be started or not:
     * - if there is balance of tokens but no position open, return true
     * @return wether to start a new epoch or not
     */
    function shouldStartEpoch() external view returns (bool) {
        // return true if we have balance of A or balance of B while the position is closed
        return
            (balanceOfA() > 0 || balanceOfB() > 0) &&
            investedA == 0 &&
            investedB == 0;
    }

    /*
     * @notice
     *  Function available for vault managers to set the boolean value deciding wether
     * to re-invest into the LP or not
     * @param _dontInvestWant, new booelan value to use
     */
    function setDontInvestWant(bool _dontInvestWant)
        external
        onlyVaultManagers
    {
        dontInvestWant = _dontInvestWant;
    }

    /*
     * @notice
     *  Function available for vault managers to set the minimum reward to harvest
     * @param _minRewardToHarvest, new value to use
     */
    function setMinRewardToHarvest(uint256 _minRewardToHarvest)
        external
        onlyVaultManagers
    {
        minRewardToHarvest = _minRewardToHarvest;
    }

    /*
     * @notice
     *  Function available for vault managers to set the minimum amount to sell
     * @param _minAmountToSell, new value to use
     */
    function setMinAmountToSell(uint256 _minAmountToSell)
        external
        onlyVaultManagers
    {
        minAmountToSell = _minAmountToSell;
    }

    /*
     * @notice
     *  Function available for vault managers to set the auto protection
     * @param _autoProtectionDisabled, new value to use
     */
    function setAutoProtectionDisabled(bool _autoProtectionDisabled)
        external
        onlyVaultManagers
    {
        autoProtectionDisabled = _autoProtectionDisabled;
    }

    /*
     * @notice
     *  Function available for vault managers to set the maximum allowed loss
     * @param _maxPercentageLoss, new value to use
     */
    function setMaxPercentageLoss(uint256 _maxPercentageLoss)
        external
        onlyVaultManagers
    {
        require(_maxPercentageLoss <= RATIO_PRECISION);
        maxPercentageLoss = _maxPercentageLoss;
    }

    /*
     * @notice
     *  Function available for providers to close the joint position and return the funds to each 
     * provider strategy
     */
    function closePositionReturnFunds() external onlyProviders {
        // Check if it needs to stop starting new epochs after finishing this one.
        // _autoProtect is implemented in children
        if (_autoProtect() && !autoProtectionDisabled) {
            dontInvestWant = true;
        }

        // Check that we have a position to close
        if (investedA == 0 || investedB == 0) {
            return;
        }

        // 1. CLOSE LIQUIDITY POSITION
        // Closing the position will:
        // - Remove liquidity from DEX
        // - Claim pending rewards
        // - Close Hedge and receive payoff
        // and returns current balance of tokenA and tokenB
        (uint256 currentBalanceA, uint256 currentBalanceB) = _closePosition();

        // 2. SELL REWARDS FOR WANT
        (uint256 rewardsSwappedToA, uint256 rewardsSwappedToB) = swapRewardTokens();
        currentBalanceA += rewardsSwappedToA;
        currentBalanceB += rewardsSwappedToB;

        // 3. REBALANCE PORTFOLIO
        // Calculate rebalance operation
        // It will return which of the tokens (A or B) we need to sell and how much of it
        // to leave the position with the initial proportions
        (address sellToken, uint256 sellAmount) = calculateSellToBalance(
            currentBalanceA,
            currentBalanceB,
            investedA,
            investedB
        );
        // Perform the swap to balance the tokens
        if (sellToken != address(0) && sellAmount > minAmountToSell) {
            uint256 buyAmount = swap(
                sellToken,
                sellToken == tokenA ? tokenB : tokenA,
                sellAmount,
                0
            );
        }

        // reset invested balances
        investedA = investedB = 0;

        _returnLooseToProviders();
        // Check that we have returned with no losses

        require(
            IERC20(tokenA).balanceOf(address(providerA)) >=
                (providerA.totalDebt() *
                    (RATIO_PRECISION - maxPercentageLoss)) /
                    RATIO_PRECISION,
            "!wrong-balanceA"
        );
        require(
            IERC20(tokenB).balanceOf(address(providerB)) >=
                (providerB.totalDebt() *
                    (RATIO_PRECISION - maxPercentageLoss)) /
                    RATIO_PRECISION,
            "!wrong-balanceB"
        );
    }
    
    /*
     * @notice
     *  Function available for providers to open the joint position:
     * - open the LP position
     * - open the hedginf position if necessary
     * - deposit the LPs if necessary
     */
    function openPosition() external onlyProviders {
        // No capital, nothing to do
        if (balanceOfA() == 0 || balanceOfB() == 0) {
            return;
        }

        require(
            balanceOfStake() == 0 &&
                balanceOfPool() == 0 &&
                investedA == 0 &&
                investedB == 0
        ); // don't create LP if we are already invested

        // Open the LP position
        (uint256 amountA, uint256 amountB) = createLP();
        // Open hedge
        (uint256 costHedgeA, uint256 costHedgeB) = hedgeLP();

        // Set invested amounts
        investedA = amountA + costHedgeA;
        investedB = amountB + costHedgeB;

        // Deposit LPs (if any)
        depositLP();

        // If there is loose balance, return it
        if (balanceOfStake() != 0 || balanceOfPool() != 0) {
            _returnLooseToProviders();
        }
    }

    // Keepers will claim and sell rewards mid-epoch (otherwise we sell only in the end)
    function harvest() external virtual onlyKeepers {
        getReward();
    }

    function harvestTrigger(uint256 callCost) external view virtual returns (bool) {
        return balanceOfRewardToken()[0] > minRewardToHarvest;
    }

    function getHedgeProfit() public view virtual returns (uint256, uint256);

    /*
     * @notice
     *  Function estimating the current assets in the joint, taking into account:
     * - current balance of tokens in the LP
     * - pending rewards from the LP (if any)
     * - hedge profit (if any)
     * - rebalancing of tokens to maintain token ratios
     * @return _aBalance, _bBalance, estimated tokenA and tokenB balances
     */
    function estimatedTotalAssetsAfterBalance()
        public
        view
        returns (uint256 _aBalance, uint256 _bBalance)
    {
        // Current status of tokens in LP (includes potential IL)
        (_aBalance, _bBalance) = balanceOfTokensInLP();

        // Add remaining balance in joint (if any)
        _aBalance = _aBalance + balanceOfA();
        _bBalance = _bBalance + balanceOfB();

        // Include hedge payoffs
        (uint256 callProfit, uint256 putProfit) = getHedgeProfit();
        _aBalance = _aBalance + callProfit;
        _bBalance = _bBalance + putProfit;

        // Include rewards (swapping them if not tokenA or tokenB)
        uint256[] memory _rewardsPending = pendingRewards();
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            address reward = rewardTokens[i];
            if (reward == tokenA) {
                _aBalance = _aBalance + _rewardsPending[i];
            } else if (reward == tokenB) {
                _bBalance = _bBalance + _rewardsPending[i];
            } else if (_rewardsPending[i] != 0) {
                address swapTo = findSwapTo(reward);
                uint256 outAmount = quote(
                    reward,
                    swapTo,
                    _rewardsPending[i] + IERC20(reward).balanceOf(address(this))
                );
                if (swapTo == tokenA) {
                    _aBalance = _aBalance + outAmount;
                } else if (swapTo == tokenB) {
                    _bBalance = _bBalance + outAmount;
                }
            }
        }

        // Calculate rebalancing operation needed
        (address sellToken, uint256 sellAmount) = calculateSellToBalance(
            _aBalance,
            _bBalance,
            investedA,
            investedB
        );

        // Update amounts with rebalancing operation
        if (sellToken == tokenA) {
            uint256 buyAmount = quote(sellToken, tokenB, sellAmount);
            _aBalance = _aBalance - sellAmount;
            _bBalance = _bBalance + buyAmount;
        } else if (sellToken == tokenB) {
            uint256 buyAmount = quote(sellToken, tokenA, sellAmount);
            _bBalance = _bBalance - sellAmount;
            _aBalance = _aBalance + buyAmount;
        }
    }

    /*
     * @notice
     *  Function available internally calculating the necessary operation to rebalance
     * the tokenA and tokenB balances to initial ratios
     * @param currentA, current balance of tokenA
     * @param currentB, current balance of tokenB
     * @param startingA, initial balance of tokenA
     * @param startingB, initial balance of tokenB
     * @return _sellToken, address of the token needed to sell
     * @return _sellAmount, amount needed to sell
     */
    function calculateSellToBalance(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) internal view returns (address _sellToken, uint256 _sellAmount) {
        // If no position, no calculation needed
        if (startingA == 0 || startingB == 0) return (address(0), 0);

        // Get the current ratio between current and starting balance for each token
        (uint256 ratioA, uint256 ratioB) = getRatios(
            currentA,
            currentB,
            startingA,
            startingB
        );

        //  if already balanced, no action needed
        if (ratioA == ratioB) return (address(0), 0);

        // If ratioA is higher, there is excess of tokenA
        if (ratioA > ratioB) {
            _sellToken = tokenA;
            // Simulate the swap and assess the received amount
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentA,
                currentB,
                startingA,
                startingB,
                10**uint256(IERC20Extended(tokenA).decimals())
            );
        } else {
            // ratioB is higher, excess of tokenB
            _sellToken = tokenB;
            // Simulate the swap and assess the received amount
            _sellAmount = _calculateSellToBalance(
                _sellToken,
                currentB,
                currentA,
                startingB,
                startingA,
                10**uint256(IERC20Extended(tokenB).decimals())
            );
        }
    }

    /*
     * @notice
     *  Function available internally calculating and simulating the necessary swap to 
     * rebalance the tokens
     * @param sellToken, address of the token to sell
     * @param current0, current balance of token
     * @param current1, current balance of other token
     * @param starting0, initial balance of token
     * @param starting1, initial balance of other token     
     * @param precision, constant value ensuring precision is preserved
     * @return _sellAmount, amount needed to sell
     */
    function _calculateSellToBalance(
        address sellToken,
        uint256 current0,
        uint256 current1,
        uint256 starting0,
        uint256 starting1,
        uint256 precision
    ) internal view returns (uint256 _sellAmount) {
        uint256 numerator = (current0 - ((starting0 * current1) / starting1)) *
            precision;
        uint256 exchangeRate = quote(
            sellToken,
            sellToken == tokenA ? tokenB : tokenA,
            precision
        );

        // First time to approximate
        _sellAmount =
            numerator /
            (precision + ((starting0 * exchangeRate) / starting1));
        // Shortcut to avoid Uniswap amountIn == 0 revert
        if (_sellAmount == 0) {
            return 0;
        }

        // Second time to account for price impact
        exchangeRate =
            (quote(
                sellToken,
                sellToken == tokenA ? tokenB : tokenA,
                _sellAmount
            ) * precision) /
            _sellAmount;
        _sellAmount =
            numerator /
            (precision + ((starting0 * exchangeRate) / starting1));
    }

    /*
     * @notice
     *  Function available publicly estimating the balance of one of the providers 
     * (one of the tokens). Re-uses the estimatedTotalAssetsAfterBalance function but oonly uses
     * one the 2 returned values
     * @param _provider, address of the provider of interest
     * @return _balance, balance of the requested provider
     */
    function estimatedTotalProviderAssets(address _provider)
        public
        view
        returns (uint256 _balance)
    {
        if (_provider == address(providerA)) {
            (_balance, ) = estimatedTotalAssetsAfterBalance();
        } else if (_provider == address(providerB)) {
            (, _balance) = estimatedTotalAssetsAfterBalance();
        }
    }

    function getHedgeBudget(address token)
        public
        view
        virtual
        returns (uint256);

    function hedgeLP() internal virtual returns (uint256, uint256);

    function closeHedge() internal virtual;

    /*
     * @notice
     *  Function available publicly estimating the balancing ratios for the 2 tokens in the form:
     * ratio = currentBalance / investedBalance
     * @param currentA, current balance of tokenA
     * @param currentB, current balance of tokenB
     * @param startingA, initial balance of tokenA
     * @param startingB, initial balance of tokenB
     * @return _a, _b, ratios for tokenA and tokenB
     */
    function getRatios(
        uint256 currentA,
        uint256 currentB,
        uint256 startingA,
        uint256 startingB
    ) public pure returns (uint256 _a, uint256 _b) {
        _a = (currentA * RATIO_PRECISION) / startingA;
        _b = (currentB * RATIO_PRECISION) / startingB;
    }

    function createLP() internal virtual returns (uint256, uint256);

    function burnLP(uint256 amount) internal virtual;

    /*
     * @notice
     *  Function available internally deciding what to swap agaisnt the requested token:
     * - if token is either tokenA or B, swap to the other
     * - if token is not A or B but is a reward, swap to the reference token if it's 
     * either A or B, if not, swap to tokenA
     * @param token, address of the token to swap from
     * @return address of the token to swap to
     */
    function findSwapTo(address from_token) internal view returns (address) {
        if (tokenA == from_token) {
            return tokenB;
        } else if (tokenB == from_token) {
            return tokenA;
        }
        if (tokenA == referenceToken || tokenB == referenceToken) {
            return referenceToken;
        }
        return tokenA;
    }

    /*
     * @notice
     *  Function available internally deciding the swapping path to follow
     * @param _token_in, address of the token to swap from
     * @param _token_to, address of the token to swap to
     * @return address array of the swap path to follow
     */
    function getTokenOutPath(address _token_in, address _token_out)
        internal
        view
        returns (address[] memory _path)
    {   
        address _tokenA = tokenA;
        address _tokenB = tokenB;
        bool isReferenceToken = _token_in == address(referenceToken) ||
            _token_out == address(referenceToken);
        bool is_internal = (_token_in == _tokenA && _token_out == _tokenB) ||
            (_token_in == _tokenB && _token_out == _tokenA);
        _path = new address[](isReferenceToken || is_internal ? 2 : 3);
        _path[0] = _token_in;
        if (isReferenceToken || is_internal) {
            _path[1] = _token_out;
        } else {
            _path[1] = address(referenceToken);
            _path[2] = _token_out;
        }
    }

    function getReward() internal virtual;

    function depositLP() internal virtual {}

    function withdrawLP() internal virtual {}

    /*
     * @notice
     *  Function available internally swapping amounts necessary to swap rewards
     * @return amounts exchanged to tokenA and tokenB
     */
    function swapRewardTokens()
        internal
        virtual
        returns (uint256 swappedToA, uint256 swappedToB)
    {
        address _tokenA = tokenA;
        address _tokenB = tokenB;
        for (uint256 i = 0; i < rewardTokens.length; i++) {
            address reward = rewardTokens[i];
            uint256 _rewardBal = IERC20(reward).balanceOf(address(this));
            // If the reward token is either A or B, don't swap
            if (reward == _tokenA || reward == _tokenB || _rewardBal == 0) {
                continue;
            // If the referenceToken is either A or B, swap rewards against it 
            } else if (_tokenA == referenceToken) {
                    swappedToA += swap(reward, referenceToken, _rewardBal, 0);
            } else if (_tokenB == referenceToken) {
                    swappedToB += swap(reward, referenceToken, _rewardBal, 0);
            } else {
                // Assume that position has already been liquidated
                (uint256 ratioA, uint256 ratioB) = getRatios(
                    balanceOfA(),
                    balanceOfB(),
                    investedA,
                    investedB
                );
                
                if (ratioA >= ratioB) {
                    swappedToB += swap(reward, _tokenB, _rewardBal, 0);
                } else {
                    swappedToA += swap(reward, _tokenA, _rewardBal, 0);
                }
            }
        }
        return (swappedToA, swappedToB);
    }

    function swap(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn,
        uint256 _minOutAmount
    ) internal virtual returns (uint256 _amountOut);

    function quote(
        address _tokenFrom,
        address _tokenTo,
        uint256 _amountIn
    ) internal view virtual returns (uint256 _amountOut);

    /*
     * @notice
     *  Function available internally closing the joint postion:
     *  - withdraw LPs (if any)
     *  - close hedging position (if any)
     *  - close LP position 
     * @return balance of tokenA and tokenB
     */
    function _closePosition() internal returns (uint256, uint256) {
        // Unstake LP from staking contract
        withdrawLP();

        // Close the hedge
        closeHedge();

        if (balanceOfPool() == 0) {
            return (0, 0);
        }

        // **WARNING**: This call is sandwichable, care should be taken
        //              to always execute with a private relay
        burnLP(balanceOfPool());

        return (balanceOfA(), balanceOfB());
    }

    /*
     * @notice
     *  Function available internally sending back all funds to provuder strategies
     * @return balance of tokenA and tokenB
     */
    function _returnLooseToProviders()
        internal
        returns (uint256 balanceA, uint256 balanceB)
    {
        balanceA = balanceOfA();
        if (balanceA > 0) {
            IERC20(tokenA).safeTransfer(address(providerA), balanceA);
        }

        balanceB = balanceOfB();
        if (balanceB > 0) {
            IERC20(tokenB).safeTransfer(address(providerB), balanceB);
        }
    }

    /*
     * @notice
     *  Function available publicly returning the joint's balance of tokenA
     * @return balance of tokenA 
     */
    function balanceOfA() public view returns (uint256) {
        return IERC20(tokenA).balanceOf(address(this));
    }

    /*
     * @notice
     *  Function available publicly returning the joint's balance of tokenB
     * @return balance of tokenB
     */
    function balanceOfB() public view returns (uint256) {
        return IERC20(tokenB).balanceOf(address(this));
    }

    function balanceOfPool() public view virtual returns (uint256);

    /*
     * @notice
     *  Function available publicly returning the joint's balance of rewards
     * @return array of balances
     */
    function balanceOfRewardToken() public view returns (uint256[] memory) {
        uint256[] memory _balances = new uint256[](rewardTokens.length);
        for (uint8 i = 0; i < rewardTokens.length; i++) {
            _balances[i] = IERC20(rewardTokens[i]).balanceOf(address(this));
        }
        return _balances;
    }

    function balanceOfStake() public view virtual returns (uint256 _balance) {}

    function balanceOfTokensInLP()
        public
        view
        virtual
        returns (uint256 _balanceA, uint256 _balanceB);

    function pendingRewards() public view virtual returns (uint256[] memory);

    // --- MANAGEMENT FUNCTIONS ---
    /*
     * @notice
     *  Function available to vault managers closing the joint position manually
     * @param expectedBalanceA, expected balance of tokenA to receive
     * @param expectedBalanceB, expected balance of tokenB to receive
     */
    function liquidatePositionManually(
        uint256 expectedBalanceA,
        uint256 expectedBalanceB
    ) external onlyVaultManagers {
        (uint256 balanceA, uint256 balanceB) = _closePosition();
        require(expectedBalanceA <= balanceA, "!sandwidched");
        require(expectedBalanceB <= balanceB, "!sandwidched");
    }

    /*
     * @notice
     *  Function available to vault managers returning the funds to the providers manually
     */
    function returnLooseToProvidersManually() external onlyVaultManagers {
        _returnLooseToProviders();
    }

    /*
     * @notice
     *  Function available to vault managers closing the LP position manually
     * @param expectedBalanceA, expected balance of tokenA to receive
     * @param expectedBalanceB, expected balance of tokenB to receive
     */
    function removeLiquidityManually(
        uint256 amount,
        uint256 expectedBalanceA,
        uint256 expectedBalanceB
    ) external virtual onlyVaultManagers {
        burnLP(amount);
        require(expectedBalanceA <= balanceOfA(), "!sandwidched");
        require(expectedBalanceB <= balanceOfB(), "!sandwidched");
    }

    function swapTokenForTokenManually(
        bool sellA,
        uint256 swapInAmount,
        uint256 minOutAmount
    ) external virtual returns (uint256);

    /*
     * @notice
     *  Function available to governance sweeping a specified token but tokenA and B
     * @param _token, address of the token to sweep
     */
    function sweep(address _token) external onlyGovernance {
        require(_token != address(tokenA));
        require(_token != address(tokenB));

        SafeERC20.safeTransfer(
            IERC20(_token),
            providerA.vault().governance(),
            IERC20(_token).balanceOf(address(this))
        );
    }

    /*
     * @notice
     *  Function available to providers to change the provider addresses
     * @param _newProvider, new address of provider
     */
    function migrateProvider(address _newProvider) external onlyProviders {
        ProviderStrategy newProvider = ProviderStrategy(_newProvider);
        if (address(newProvider.want()) == tokenA) {
            providerA = newProvider;
        } else if (address(newProvider.want()) == tokenB) {
            providerB = newProvider;
        } else {
            revert("Unsupported token");
        }
    }

    /*
     * @notice
     *  Internal function checking if allowance is already enough for the contract
     * and if not, safely sets it to max
     * @param _contract, spender contract
     * @param _token, token to approve spend
     * @param _amount, _amoun to approve
     */
    function _checkAllowance(
        address _contract,
        IERC20 _token,
        uint256 _amount
    ) internal {
        if (_token.allowance(address(this), _contract) < _amount) {
            _token.safeApprove(_contract, 0);
            _token.safeApprove(_contract, _amount);
        }
    }
}
