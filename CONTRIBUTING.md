# Contributing

Thanks for helping make AI claims checkable.

## Setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,all]"
pytest                    # full suite (extras-dependent tests skip if an extra is missing)
ruff check src tests examples scripts
python scripts/gen_docs.py   # whenever metrics, profiles, mappings or schemas change
```
Contracts (optional): `cd contracts && npm install && node scripts/compile.js --bytecode artifacts/contracts.json`.

## Rules of the road
* **A new metric ships with**: a formal spec (`@metric(...)` with assumptions *and* limitations), a flaw-injection test that proves it detects what it claims, regenerated docs, and — if it
  maps to a regulatory theme — a mapping entry. Start it as `maturity="research"`.
* **Never edit a metric's definition in place** — add `_v2`.
* **Untested ≠ passed**: if inputs are missing, return `untested(...)`; never return a default value.
* **No silent fallbacks** for optional backends; raise `BackendUnavailable`.
* **Core stays stdlib-only.** Third-party imports go behind lazy imports and an extra.
* **Claims**: anything you assert in docs must appear in `docs/CLAIMS.md` with its verification, or be removed. No performance, compliance or "most advanced" language.
* **Secrets**: never commit keys; examples read keys from env vars.
* Keep Python 3.10 compatible syntax (no nested same-quote f-strings, no 3.11+ only syntax).

## Pull requests
Small, focused, with tests. Describe user-visible changes in `CHANGELOG.md`. Security issues: see `SECURITY.md` (do not open a public issue).
