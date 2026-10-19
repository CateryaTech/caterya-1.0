import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = sorted((ROOT / "examples").glob("0*.py"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_runs(path):
    if path.name.startswith("08"):
        pytest.importorskip("web3")
        pytest.importorskip("eth_tester")
        pytest.importorskip("cryptography")
    r = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}, timeout=120)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-1500:]


def test_ci_gate_example_blocks_a_bad_build():
    ok = subprocess.run([sys.executable, str(ROOT / "examples/05_ci_gate.py")], capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    bad = subprocess.run([sys.executable, str(ROOT / "examples/05_ci_gate.py"), "--flaws", "pii,injection"], capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"})
    assert ok.returncode == 0 and bad.returncode == 1 and "GATE: FAIL" in bad.stdout
