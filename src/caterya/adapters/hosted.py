"""Hosted-model adapters (OpenAI-compatible, Anthropic Messages API) and Hugging Face (local)."""
from __future__ import annotations

import os
from typing import Optional

from ..core.errors import BackendUnavailable
from .base import ModelAdapter
from .net import post_json


class OpenAICompatAdapter(ModelAdapter):
    """Any server exposing ``POST {base_url}/chat/completions`` (OpenAI, vLLM, Ollama, LM Studio, ...)."""

    def __init__(self, model: str, base_url: str = "https://api.openai.com/v1", api_key_env: str = "OPENAI_API_KEY",
                 allow_local: bool = False, temperature: float = 0.0, name: str = "openai-compat"):
        self.model, self.base_url, self.api_key_env = model, base_url.rstrip("/"), api_key_env
        self.allow_local, self.temperature, self.name = allow_local, temperature, name

    def capabilities(self):
        return frozenset({"generate"})

    def generate(self, prompt, *, system=None, seed=None):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": msgs, "temperature": self.temperature}
        if seed is not None:
            body["seed"] = seed
        headers = {}
        key = os.environ.get(self.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        out = post_json(f"{self.base_url}/chat/completions", body, headers, allow_local=self.allow_local)
        return out["choices"][0]["message"]["content"] or ""


class AnthropicAdapter(ModelAdapter):
    """Anthropic Messages API. Set ``ANTHROPIC_API_KEY``; pass the model id you want evaluated."""

    def __init__(self, model: Optional[str] = None, api_key_env: str = "ANTHROPIC_API_KEY", max_tokens: int = 1024,
                 base_url: str = "https://api.anthropic.com", allow_local: bool = False, name: str = "anthropic"):
        self.model = model or os.environ.get("CATERYA_ANTHROPIC_MODEL", "")
        if not self.model:
            raise ValueError("pass model=... or set CATERYA_ANTHROPIC_MODEL (see docs.claude.com for current model ids)")
        self.api_key_env, self.max_tokens, self.base_url, self.name = api_key_env, max_tokens, base_url.rstrip("/"), name
        self.allow_local = allow_local

    def capabilities(self):
        return frozenset({"generate"})

    def generate(self, prompt, *, system=None, seed=None):
        key = os.environ.get(self.api_key_env, "")
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        out = post_json(f"{self.base_url}/v1/messages", body, {"x-api-key": key, "anthropic-version": "2023-06-01"}, allow_local=self.allow_local)
        return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


class HuggingFaceAdapter(ModelAdapter):
    """Local ``transformers`` text-generation pipeline (extra: ``caterya[hf]``)."""

    def __init__(self, model: str, max_new_tokens: int = 128, name: str = "huggingface"):
        try:
            from transformers import pipeline
        except Exception as e:  # pragma: no cover
            raise BackendUnavailable("transformers not installed: pip install 'caterya[hf]'") from e
        self._pipe = pipeline("text-generation", model=model)
        self.max_new_tokens, self.name = max_new_tokens, name

    def capabilities(self):
        return frozenset({"generate"})

    def generate(self, prompt, *, system=None, seed=None):  # pragma: no cover - needs model weights
        text = (system + "\n\n" if system else "") + prompt
        out = self._pipe(text, max_new_tokens=self.max_new_tokens, do_sample=False, return_full_text=False)
        return out[0]["generated_text"]
