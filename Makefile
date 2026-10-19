.PHONY: install test lint docs contracts demo serve core-test clean
install:   ; pip install -e ".[dev,all]"
test:      ; pytest
core-test: ; python -m venv /tmp/caterya-core && /tmp/caterya-core/bin/pip install -q -e . pytest && /tmp/caterya-core/bin/pytest
lint:      ; ruff check src tests examples scripts
docs:      ; python scripts/gen_docs.py
contracts: ; cd contracts && npm install --no-audit --no-fund && node scripts/compile.js --bytecode artifacts/contracts.json
demo:      ; caterya demo --flaws pii,bias --out out/ && caterya evidence verify out/bundle.json
serve:     ; caterya serve --host 127.0.0.1 --port 8000
clean:     ; rm -rf build dist .pytest_cache .ruff_cache src/*.egg-info out
