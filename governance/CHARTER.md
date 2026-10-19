# Project charter

**Mission.** Provide open, vendor-neutral infrastructure that makes claims about AI systems *checkable*: what was measured, how, by whom, and what was not.

## Principles
1. Evidence before assertions; gaps are shown, never hidden.
2. Humans decide; software recommends. Decisions are named, signed and reversible.
3. Independence is structural (separate keys, separate parties), not rhetorical.
4. We state limitations and maturity with every release; we do not make performance, compliance or safety claims we cannot verify.
5. Vendor neutrality: no adapter, backend or chain is privileged.

## Roles
* **Maintainers** — merge changes, cut releases, keep the claims ledger and generated docs current. Initial maintainer: Ary H Haryanto (Caterya Tech).
* **Reviewers** — independent reviewers sign off on promoting a metric from *research* to *stable* (see `docs/VALIDATION_PROTOCOL.md`).
* **Attesters / evaluators** — parties admitted under `ACCREDITATION.md`; they are users of the project, not governors of it.

## Changes that need extra care
* Evidence/hashing/signature formats: bump `caterya.evidence/vN`, document in the changelog, provide a verifier for the previous version.
* Metric definitions: a changed definition is a new metric version (`_v2`), never an in-place edit.
* Contracts: require an independent review before any release is called deployable; breaking changes ship as new contracts, not upgrades.
* Anything touching the honesty policy (README, `docs/CLAIMS.md`): requires a maintainer plus one other reviewer.

## Conflicts of interest
Maintainers who evaluate or decide on their own systems must say so in the evidence (`SystemConfig.owner`) and cannot count as the independent party at L3/L4.

## Succession
If the sole maintainer becomes unavailable, repository admin rights pass to the two longest-standing reviewers; if none exist, the project should be handed to a recognised open-source foundation or archived with a clear notice.
