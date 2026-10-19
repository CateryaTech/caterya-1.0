// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Read-only interface DeFi protocols integrate against.
interface ICateryaAssuranceGate {
    /// @return true iff `systemHash` has a non-revoked, non-expired attestation of level >= `minLevel`.
    function isAssured(bytes32 systemHash, uint8 minLevel) external view returns (bool);
}
