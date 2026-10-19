# CATERYA contracts (UNAUDITED reference implementations)

| file | purpose |
|---|---|
| `Owned2Step.sol` | two-step ownership |
| `CateryaAnchorRegistry.sol` | public timestamp log of evidence Merkle roots |
| `CateryaAssuranceGate.sol` | attestations by system hash; `isAssured(systemHash, minLevel)` |
| `CateryaEvaluatorBond.sol` | evaluator bonds with delayed withdrawal and arbiter slashing |
| `interfaces/ICateryaAssuranceGate.sol` | consumer interface |
| `examples/AssuranceGatedPool.sol` | illustration of a gated consumer |

`npm install && npm run compile` rebuilds `artifacts/contracts.json` and the ABIs under `src/caterya/blockchain/abi/`.
Read `docs/BLOCKCHAIN_DEFI.md` (trust model, oracle problem, deployment checklist) before deploying. Tested on an in-process EVM only.
