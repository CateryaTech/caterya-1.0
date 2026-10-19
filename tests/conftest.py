import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from caterya import AssuranceEngine, SystemConfig  # noqa: E402
from caterya.metrics.context import TabularData  # noqa: E402


@pytest.fixture
def system():
    return SystemConfig("test-sys", "1.0", provider="mock", model_id="m1", owner="Acme", intended_use="testing", description="test system")


@pytest.fixture
def engine(system):
    return AssuranceEngine(system)


def make_tabular(n=600, bias=0.0, seed=1, with_labels=True):
    rnd = random.Random(seed)
    groups = [rnd.choice(["A", "B"]) for _ in range(n)]
    y = [int(rnd.random() < 0.5) for _ in range(n)]
    prob = [min(1.0, max(0.0, 0.5 * yi + 0.25 + rnd.gauss(0, 0.12) - (bias if g == "B" else 0.0))) for yi, g in zip(y, groups)]
    X = [{"x1": rnd.gauss(0, 1), "x2": rnd.gauss(0, 1), "x3": rnd.gauss(0, 1), "group": g} for g in groups]
    return TabularData(y_true=y if with_labels else None, y_prob=prob, groups={"group": groups}, X=X)


@pytest.fixture
def tab_fair():
    return make_tabular(bias=0.0)


@pytest.fixture
def tab_biased():
    return make_tabular(bias=0.25)
