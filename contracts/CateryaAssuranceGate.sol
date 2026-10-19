// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Owned2Step} from "./Owned2Step.sol";
import {ICateryaAssuranceGate} from "./interfaces/ICateryaAssuranceGate.sol";

/// @title CateryaAssuranceGate
/// @notice On-chain registry of CATERYA assurance attestations, keyed by system hash, so that other
///         contracts can condition behaviour on "this AI system holds assurance level >= N".
/// @dev    The level describes the depth/independence of an off-chain assurance PROCESS. It is not a
///         safety guarantee. Who may attest is a governance decision (see docs/BLOCKCHAIN_DEFI.md).
///         UNAUDITED reference implementation.
contract CateryaAssuranceGate is Owned2Step, ICateryaAssuranceGate {
    uint8 public constant MAX_LEVEL = 4;

    struct Attestation {
        uint8 level;
        bytes32 carHash;
        uint64 issuedAt;
        uint64 expiresAt;
        address attester;
        bool revoked;
    }

    mapping(address => bool) public attesters;
    mapping(bytes32 => Attestation) private _att;

    event AttesterSet(address indexed who, bool allowed);
    event Attested(bytes32 indexed systemHash, uint8 level, bytes32 carHash, uint64 expiresAt, address indexed attester);
    event Revoked(bytes32 indexed systemHash, address indexed by, string reason);

    error NotAttester();
    error BadLevel();
    error BadExpiry();
    error NotAllowedToRevoke();
    error NoAttestation();

    function setAttester(address who, bool allowed) external onlyOwner {
        attesters[who] = allowed;
        emit AttesterSet(who, allowed);
    }

    function attest(bytes32 systemHash, uint8 level, bytes32 carHash, uint64 expiresAt) external {
        if (!attesters[msg.sender]) revert NotAttester();
        if (level > MAX_LEVEL) revert BadLevel();
        if (expiresAt <= block.timestamp) revert BadExpiry();
        _att[systemHash] = Attestation(level, carHash, uint64(block.timestamp), expiresAt, msg.sender, false);
        emit Attested(systemHash, level, carHash, expiresAt, msg.sender);
    }

    /// @notice The issuing attester or the owner may revoke (e.g. after an incident).
    function revoke(bytes32 systemHash, string calldata reason) external {
        Attestation storage a = _att[systemHash];
        if (a.attester == address(0)) revert NoAttestation();
        if (msg.sender != a.attester && msg.sender != owner) revert NotAllowedToRevoke();
        a.revoked = true;
        emit Revoked(systemHash, msg.sender, reason);
    }

    function isAssured(bytes32 systemHash, uint8 minLevel) public view returns (bool) {
        Attestation storage a = _att[systemHash];
        return a.attester != address(0) && !a.revoked && a.expiresAt > block.timestamp && a.level >= minLevel && attesters[a.attester];
    }

    function getAttestation(bytes32 systemHash) external view returns (Attestation memory) {
        return _att[systemHash];
    }
}
