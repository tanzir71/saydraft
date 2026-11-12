"""Text-only cleanup over the owned streaming sidecar; failures preserve rules."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .loopback import LocalHTTPError
from .prompts import PromptHints, bridge_protected, build_messages, output_token_limit
from .sidecar import SidecarReply
from .streaming import read_completion
from .structure import rule_structure_reason


@dataclass(frozen=True)
class CleanupReply:
    text: str | None
    reason: str
    input_tokens: int = 0
    output_limit: int = 0


class CleanupClient:
    def __init__(self, manager, *, max_tokens=256, clock=time.monotonic):
        if type(max_tokens) is not int or max_tokens < 1:
            raise ValueError("Cleanup output cap must be a positive integer")
        self.manager, self.max_tokens, self.clock = manager, max_tokens, clock

    def _request(self, text, *, hints=None, glossary=(), timeout=0.8, max_tokens=None):
        try:
            messages = build_messages(text, hints=hints, glossary=glossary)
        except (OSError, ValueError):
            return SidecarReply(None, "prompt_unavailable")

        def operation(client, deadline):
            def check():
                if self.clock() >= deadline:
                    raise TimeoutError("Cleanup deadline expired")

            tokens = client.request_json("/tokenize", payload={"content": text, "add_special": False},
                                         deadline=deadline).get("tokens")
            if not isinstance(tokens, list) or any(type(token) is not int or token < 0 for token in tokens):
                raise LocalHTTPError("Local tokenizer returned unsupported tokens")
            limit = min(self.max_tokens if max_tokens is None else max_tokens, output_token_limit(len(tokens)))
            payload = {"model": "saydraft-cleanup", "messages": messages, "stream": True, "n": 1,
                "temperature": 0, "max_tokens": limit, "stop": ["</out>"], "cache_prompt": True,
                "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none"}
            with client.response_bytes("/v1/chat/completions", payload=payload, deadline=deadline,
                                       content_type="text/event-stream") as chunks:
                result = read_completion(chunks, check)
            return {**result, "input_tokens": len(tokens), "output_limit": limit}

        return self.manager.run(operation, timeout=timeout)

    def prepare_prompt(self, *, style="neutral", post_rules=True, app="", group="general", timeout=60):
        # A fixed one-token probe warms the real chat prefix, never user content.
        reply = self._request("Ready", hints=PromptHints(style=style, post_rules=post_rules, app=app, group=group),
                              timeout=timeout, max_tokens=1)
        value = reply.value or {}
        complete = (value.get("done") and value.get("finish_reason") in ("stop", "length")
                    and not value.get("tool_calls") and value.get("input_tokens", 0) > 0)
        reason = "prepared" if complete else reply.reason if reply.reason != "ok" else "prompt_incomplete"
        return CleanupReply(None, reason)

    def clean(self, text, *, hints=None, glossary=(), timeout=0.8):
        if not text.strip():
            return CleanupReply(None, "empty")
        protected = bridge_protected(text)
        reply = self._request(protected.text, hints=hints, glossary=glossary, timeout=timeout)
        if reply.value is None:
            return CleanupReply(None, reply.reason)
        value = reply.value
        counts = {"input_tokens": value.get("input_tokens", 0), "output_limit": value.get("output_limit", 0)}
        if not value.get("done") or value.get("finish_reason") != "stop":
            return CleanupReply(None, "incomplete", **counts)
        if value.get("tool_calls"):
            return CleanupReply(None, "tool_output", **counts)
        candidate = value.get("text")
        if not isinstance(candidate, str) or not candidate.strip():
            return CleanupReply(None, "empty", **counts)
        restored = protected.restore(candidate.strip())
        if restored is None:
            return CleanupReply(None, "protected_changed", **counts)
        if hints is not None and hints.post_rules:
            reason = rule_structure_reason(text, restored)
            if reason:
                return CleanupReply(None, reason, **counts)
        return CleanupReply(restored, "ok", **counts)
