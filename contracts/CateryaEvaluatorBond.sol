// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Owned2Step} from "./Owned2Step.sol";

/// @title CateryaEvaluatorBond
/// @notice Economic skin-in-the-game for evaluators: stake a bond, withdraw only after a delay, and be
///         slashable by an arbiter when evidence they signed is shown to be false.
/// @dev    The arbiter is a trusted, governance-chosen role: slashing decisions are NOT trustless.
///         No token is issued; the bond is the chain's native currency. UNAUDITED reference implementation.
contract CateryaEvaluatorBond is Owned2Step {
    struct Bond {
        uint256 amount;
        uint64 unlockAt; // 0 = not withdrawing
    }

    uint256 public immutable minBond;
    uint64 public immutable withdrawDelay;
    address public arbiter;
    address public treasury;
    mapping(address => Bond) public bonds;
    bool private _locked;

    event Deposited(address indexed evaluator, uint256 amount, uint256 total);
    event WithdrawRequested(address indexed evaluator, uint64 unlockAt);
    event Withdrawn(address indexed evaluator, uint256 amount);
    event Slashed(address indexed evaluator, uint256 amount, bytes32 indexed evidenceHash);
    event ArbiterSet(address indexed arbiter);
    event TreasurySet(address indexed treasury);

    error NotArbiter();
    error Reentrancy();
    error NothingToWithdraw();
    error StillLocked();
    error AmountTooLarge();
    error TransferFailed();
    error ZeroAddress();

    modifier nonReentrant() {
        if (_locked) revert Reentrancy();
        _locked = true;
        _;
        _locked = false;
    }

    constructor(uint256 minBond_, uint64 withdrawDelay_, address arbiter_, address treasury_) {
        if (arbiter_ == address(0) || treasury_ == address(0)) revert ZeroAddress();
        minBond = minBond_;
        withdrawDelay = withdrawDelay_;
        arbiter = arbiter_;
        treasury = treasury_;
    }

    function setArbiter(address a) external onlyOwner {
        if (a == address(0)) revert ZeroAddress();
        arbiter = a;
        emit ArbiterSet(a);
    }

    function setTreasury(address t) external onlyOwner {
        if (t == address(0)) revert ZeroAddress();
        treasury = t;
        emit TreasurySet(t);
    }

    /// @notice Depositing cancels any pending withdrawal request.
    function deposit() external payable {
        Bond storage b = bonds[msg.sender];
        b.amount += msg.value;
        b.unlockAt = 0;
        emit Deposited(msg.sender, msg.value, b.amount);
    }

    function requestWithdraw() external {
        Bond storage b = bonds[msg.sender];
        if (b.amount == 0) revert NothingToWithdraw();
        b.unlockAt = uint64(block.timestamp) + withdrawDelay;
        emit WithdrawRequested(msg.sender, b.unlockAt);
    }

    function withdraw() external nonReentrant {
        Bond storage b = bonds[msg.sender];
        if (b.amount == 0 || b.unlockAt == 0) revert NothingToWithdraw();
        if (block.timestamp < b.unlockAt) revert StillLocked();
        uint256 amt = b.amount;
        b.amount = 0;
        b.unlockAt = 0;
        (bool ok, ) = msg.sender.call{value: amt}("");
        if (!ok) revert TransferFailed();
        emit Withdrawn(msg.sender, amt);
    }

    function slash(address evaluator, uint256 amount, bytes32 evidenceHash) external nonReentrant {
        if (msg.sender != arbiter) revert NotArbiter();
        Bond storage b = bonds[evaluator];
        if (amount > b.amount) revert AmountTooLarge();
        b.amount -= amount;
        (bool ok, ) = treasury.call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Slashed(evaluator, amount, evidenceHash);
    }

    function isBonded(address evaluator) external view returns (bool) {
        Bond storage b = bonds[evaluator];
        return b.amount >= minBond && b.unlockAt == 0;
    }
}
