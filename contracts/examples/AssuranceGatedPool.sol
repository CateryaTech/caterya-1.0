// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {ICateryaAssuranceGate} from "../interfaces/ICateryaAssuranceGate.sol";

/// @notice ILLUSTRATION ONLY: a vault that lets an AI "manager" system act only while it holds a
///         sufficient, unexpired, unrevoked CATERYA attestation. Not a production vault.
contract AssuranceGatedPool {
    ICateryaAssuranceGate public immutable gate;
    uint8 public immutable minLevel;
    address public admin;
    bytes32 public managerSystemHash;

    event ManagerSet(bytes32 indexed systemHash);
    event Executed(bytes32 indexed systemHash, bytes32 indexed action);

    error NotAdmin();
    error NotAssured();
    error WrongManager();

    constructor(ICateryaAssuranceGate gate_, uint8 minLevel_) {
        gate = gate_;
        minLevel = minLevel_;
        admin = msg.sender;
    }

    function setManager(bytes32 systemHash) external {
        if (msg.sender != admin) revert NotAdmin();
        if (!gate.isAssured(systemHash, minLevel)) revert NotAssured();
        managerSystemHash = systemHash;
        emit ManagerSet(systemHash);
    }

    /// @dev Re-checks assurance on EVERY call, so a revocation or expiry takes effect immediately.
    function execute(bytes32 action) external {
        if (managerSystemHash == bytes32(0)) revert WrongManager();
        if (!gate.isAssured(managerSystemHash, minLevel)) revert NotAssured();
        emit Executed(managerSystemHash, action);
    }
}
