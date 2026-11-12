from __future__ import annotations

import threading
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from saydraft.cleanup.llm.client import CleanupClient
from saydraft.cleanup.llm.prompts import PromptHints, STYLES, user_message
from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager
from saydraft.cleanup.llm.preparation import PromptPreparation
from saydraft.cleanup.llm.gate import MIN_REQUEST_SECONDS, decision, request_timeout, score_need

logger = logging.getLogger(__name__)


def _style(tone_hint):
    return tone_hint if tone_hint in STYLES else "neutral"


def build_cleanup_prompt(text: str, *, tone_hint: str = "neutral") -> str:
    """Compatibility helper for the final plain-text contract's user message."""
    return user_message(text, PromptHints(style=_style(tone_hint)))


@dataclass(frozen=True)
class LocalLLMConfig:
    enabled: bool = False
    model_path: str = ""
    n_ctx: int = 4096
    max_tokens: int = 256
    temperature: float = 0.05
    top_p: float = 0.9
    n_threads: Optional[int] = None
    n_gpu_layers: Optional[int] = None
    backend: str = "cpu"
    timeout_ms: int = 800
    idle_seconds: int = 900
    prepare_prompt: bool = True
    budget_gate: bool = True


class LocalLLMCleaner:
    def __init__(self, cfg: LocalLLMConfig, *, manager_factory=SidecarManager, client_factory=CleanupClient,
                 clock=time.monotonic):
        self.cfg = cfg
        self._manager_factory, self._client_factory = manager_factory, client_factory
        self._manager = self._client = self._preparation = None
        self._lock = threading.Lock()
        self._closed = False
        self._clock, self.last_gate_info = clock, None

    def available(self) -> bool:
        return bool(self.cfg.enabled and self.cfg.model_path and not self._closed)

    def _get_client(self):
        with self._lock:
            if not self.available():
                return None
            if self._client is None:
                if (type(self.cfg.timeout_ms) is not int or self.cfg.timeout_ms <= 0
                        or type(self.cfg.prepare_prompt) is not bool or type(self.cfg.budget_gate) is not bool):
                    raise ValueError("Cleanup timing/preparation configuration is invalid")
                config = SidecarConfig(Path(self.cfg.model_path).resolve(), backend=self.cfg.backend,
                    threads=self.cfg.n_threads if self.cfg.n_threads is not None else 4,
                    context_size=self.cfg.n_ctx, idle_seconds=self.cfg.idle_seconds,
                    startup_seconds=60 if self.cfg.prepare_prompt else 15)
                manager = self._manager_factory(config)
                try:
                    client = self._client_factory(manager, max_tokens=self.cfg.max_tokens, clock=self._clock)
                except Exception:
                    manager.close()
                    raise
                self._manager, self._client = manager, client
                if self.cfg.prepare_prompt:
                    self._preparation = PromptPreparation(client)
            return self._client

    def warm(self):
        return self._warm(PromptHints(post_rules=True))

    def warm_for_context(self, context):
        if context.mode == "raw" or context.profile == "code/comments" or context.app_group == "code":
            return False
        return self._warm(PromptHints(style={"email": "formal", "chat": "casual"}.get(context.profile, "neutral"),
                                      post_rules=True, app=context.app_title or "", group=context.app_group))

    def _warm(self, hints):
        try:
            client = self._get_client()
            return bool(client is not None and (self._preparation.request(hints) if self._preparation is not None
                                                else client.manager.warm()))
        except Exception:
            return False

    def close(self):
        with self._lock:
            self._closed = True
            manager = self._manager
            preparation = self._preparation
        if manager is not None:
            manager.close()
        if preparation is not None:
            preparation.close()

    def _clean(self, text, hints, glossary=(), *, need=None, deadline=None):
        try:
            if not self.available():
                return None, "disabled"
            timeout = self.cfg.timeout_ms / 1000
            stop_at = None
            if need is not None:
                now = self._clock()
                timeout = request_timeout(self.cfg.timeout_ms, now=now, deadline=deadline)
                stop_at = now + timeout
                if need.score < 2 or timeout <= MIN_REQUEST_SECONDS:
                    reason = "skip_low_need" if need.score < 2 else "skip_budget"
                    self._gate_log(decision(need, reason, remaining=timeout))
                    return None, reason
            client = self._get_client()
            if client is None:
                return None, "disabled"
            if self._preparation is not None and not self._preparation.ready(hints):
                requested = self._preparation.request(hints)
                if need is not None:
                    self._gate_log(decision(need, "prompt_warming" if requested else "prompt_unprepared", remaining=timeout))
                return None, "prompt_warming" if requested else "prompt_unprepared"
            options = {"gate": need, "stop_at": stop_at} if need is not None else {}
            reply = client.clean(text, hints=hints, glossary=glossary, timeout=timeout, **options)
            if need is not None:
                info = getattr(reply, "gate", None) or decision(need, reply.reason,
                    remaining=max(0.0, stop_at - self._clock()))
                self._gate_log({**info, "outcome": reply.reason})
            if reply.reason == "skip_unprepared_prefix" and self._preparation is not None:
                self._preparation.invalidate()
                self._preparation.request(hints)
            if self._closed:
                return None, "closed"
            return reply.text, reply.reason
        except Exception:
            return None, "unavailable"

    def _gate_log(self, info):
        self.last_gate_info = info
        logger.info("Cleanup gate: %s", info)

    def clean_with_context(self, text, *, context, glossary=()):
        return self.clean_after_rules(text, context=context, raw_text=text, glossary=glossary)

    def clean_after_rules(self, text, *, context, raw_text, glossary=()):
        self.last_gate_info = None
        tone = {"email": "formal", "chat": "casual"}.get(context.profile, "neutral")
        hints = PromptHints(app=context.app_title or "", group=context.app_group, style=tone,
            intensity=context.intensity if context.intensity is not None else 4 if context.mode == "aggressive" else 3,
            language=context.language, before_caret=context.before_caret, post_rules=True)
        need = score_need(raw_text, style=tone, intensity=hints.intensity) if (
            self.cfg.budget_gate and self.cfg.prepare_prompt) else None
        return self._clean(text, hints, glossary, need=need, deadline=getattr(context, "cleanup_deadline", None))

    def clean(self, text: str, *, tone_hint: str = "neutral") -> Tuple[Optional[str], str]:
        self.last_gate_info = None
        return self._clean(text, PromptHints(style=_style(tone_hint)))

