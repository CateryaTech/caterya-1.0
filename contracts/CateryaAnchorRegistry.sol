// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {Owned2Step} from "./Owned2Step.sol";

/// @title CateryaAnchorRegistry
/// @notice Append-only public timestamp log for CATERYA evidence Merkle roots.
///         It proves "this root existed no later than block time T" - nothing more.
///         Evidence itself stays off-chain; only the 32-byte root and a URI are stored.
/// @dev    UNAUDITED reference implementation. See docs/BLOCKCHAIN_DEFI.md.
contract CateryaAnchorRegistry is Owned2Step {
    struct Anchor {
        bytes32 root;
        uint64 size;
        uint64 timestamp;
        address by;
        string uri;
    }

    Anchor[] private _anchors;
    mapping(address => bool) public anchorers;
    mapping(bytes32 => uint256) private _firstIndexPlusOne;

    event Anchored(uint256 indexed index, bytes32 indexed root, uint64 size, address indexed by, string uri);
    event AnchorerSet(address indexed who, bool allowed);

    error NotAnchorer();
    error ZeroRoot();
    error IndexOutOfRange();

    constructor() {
        anchorers[msg.sender] = true;
        emit AnchorerSet(msg.sender, true);
    }

    function setAnchorer(address who, bool allowed) external onlyOwner {
        anchorers[who] = allowed;
        emit AnchorerSet(who, allowed);
    }

    function anchorRoot(bytes32 root, uint64 size, string calldata uri) external returns (uint256 index) {
        if (!anchorers[msg.sender]) revert NotAnchorer();
        if (root == bytes32(0)) revert ZeroRoot();
        index = _anchors.length;
        _anchors.push(Anchor(root, size, uint64(block.timestamp), msg.sender, uri));
        if (_firstIndexPlusOne[root] == 0) _firstIndexPlusOne[root] = index + 1;
        emit Anchored(index, root, size, msg.sender, uri);
    }

    function anchorsLength() external view returns (uint256) {
        return _anchors.length;
    }

    function getAnchor(uint256 index) external view returns (Anchor memory) {
        if (index >= _anchors.length) revert IndexOutOfRange();
        return _anchors[index];
    }

    /// @return anchored whether the root was ever anchored; firstTimestamp the earliest block time.
    function isAnchored(bytes32 root) external view returns (bool anchored, uint64 firstTimestamp) {
        uint256 i = _firstIndexPlusOne[root];
        if (i == 0) return (false, 0);
        return (true, _anchors[i - 1].timestamp);
    }
}
