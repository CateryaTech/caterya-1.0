"""Exception hierarchy. Every failure mode is explicit; nothing is swallowed silently."""


class CateryaError(Exception):
    """Base class for all CATERYA errors."""


class VerificationError(CateryaError):
    """Evidence, chain, proof or signature failed verification."""


class BackendUnavailable(CateryaError):
    """An optional backend (quantum, EVM, IPFS, ...) is not installed or reachable.

    CATERYA never substitutes another backend silently: the caller must choose.
    """


class GovernanceError(CateryaError):
    """A governance rule (named decider, separation of duties, ...) was violated."""


class PolicyViolation(CateryaError):
    """A configured policy (egress allow-list, standing authorization, ...) was violated."""
