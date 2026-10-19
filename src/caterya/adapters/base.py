"""Model adapter interface. Adapters wrap *systems*; CATERYA only ever calls these methods."""
from __future__ import annotations

from typing import Any, Callable, Dict, FrozenSet, List, Optional


class ModelAdapter:
    name = "adapter"

    def capabilities(self) -> FrozenSet[str]:
        return frozenset()

    def generate(self, prompt: str, *, system: Optional[str] = None, seed: Optional[int] = None) -> str:
        raise NotImplementedError("this adapter does not support generate()")

    def predict(self, rows: List[Dict[str, Any]]) -> List[float]:
        raise NotImplementedError("this adapter does not support predict()")

    def explain(self, row: Dict[str, Any]) -> Dict[str, float]:
        raise NotImplementedError("this adapter does not support explain()")

    def run_agent(self, task: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("this adapter does not support run_agent()")

    def describe(self) -> Dict[str, Any]:
        return {"adapter": self.name, "capabilities": sorted(self.capabilities())}


class CallableAdapter(ModelAdapter):
    """Wrap plain Python callables — the easiest integration path."""

    def __init__(self, generate: Optional[Callable[..., str]] = None, predict: Optional[Callable[[List[Dict[str, Any]]], List[float]]] = None,
                 explain: Optional[Callable[[Dict[str, Any]], Dict[str, float]]] = None, run_agent: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
                 name: str = "callable"):
        self.name = name
        self._g, self._p, self._e, self._a = generate, predict, explain, run_agent

    def capabilities(self):
        return frozenset(c for c, f in (("generate", self._g), ("predict", self._p), ("explain", self._e), ("agent", self._a)) if f)

    def generate(self, prompt, *, system=None, seed=None):
        try:
            return self._g(prompt, system=system, seed=seed)
        except TypeError:
            return self._g(prompt)

    def predict(self, rows):
        return self._p(rows)

    def explain(self, row):
        return self._e(row)

    def run_agent(self, task):
        return self._a(task)
