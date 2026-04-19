"""Single entry point for every Anthropic API call.

Keeping everything in one place means:
 - consistent prompt caching (the project context pack is always the
   cached chunk, the user message is never cached)
 - consistent cost logging
 - one place to swap model versions when Anthropic ships a new one
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from anthropic import Anthropic

from ..config import get_settings
from ..database import SessionLocal
from ..models import AppSetting, CostLog
from .crypto import decrypt
from .prompts import SYSTEM_BY_FEATURE

logger = logging.getLogger(__name__)

_settings = get_settings()


def _api_key() -> str:
    """Prefer DB-stored key (set via Settings UI), fall back to env."""
    with SessionLocal() as db:
        row = db.get(AppSetting, 1)
        if row and row.anthropic_api_key_ct:
            try:
                return decrypt(row.anthropic_api_key_ct)
            except Exception:
                logger.warning("stored anthropic key failed to decrypt — falling back to env")
    return _settings.ANTHROPIC_API_KEY


def _get_client() -> Anthropic:
    key = _api_key()
    if not key or key == "sk-ant-REPLACE_ME":
        raise RuntimeError(
            "No Anthropic API key configured. Set one in Settings → Claude API key, "
            "or edit ANTHROPIC_API_KEY in /opt/odoopiai/.env."
        )
    return Anthropic(api_key=key)


def _log_cost(
    feature: str,
    model: str,
    usage: dict[str, int],
    user_id: int | None,
) -> None:
    with SessionLocal() as db:
        db.add(
            CostLog(
                user_id=user_id,
                feature=feature,
                model=model,
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            )
        )
        db.commit()


def _extract_usage(message) -> dict[str, int]:
    u = getattr(message, "usage", None)
    if u is None:
        return {}
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _text_from(message) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts)


def _model_for(feature: str) -> str:
    # Digests are cheap and small — use Haiku. Everything else uses the
    # configured model (DB override if set, else env default).
    if feature == "digest":
        return _settings.CLAUDE_FAST_MODEL
    with SessionLocal() as db:
        row = db.get(AppSetting, 1)
        if row and row.anthropic_model:
            return row.anthropic_model
    return _settings.CLAUDE_MODEL


def call(
    *,
    feature: str,
    user_message: str,
    project_context: dict[str, Any] | None = None,
    user_id: int | None = None,
    max_tokens: int = 2000,
    expect_json: bool = False,
) -> tuple[str, dict[str, int]]:
    """Blocking (non-streaming) call. Returns (text, usage).

    The project_context dict is serialized deterministically (sort_keys) so
    the cache breakpoint stays stable across calls for the same project.
    """
    system_prompt = SYSTEM_BY_FEATURE[feature]
    model = _model_for(feature)

    # Build the messages. Cache breakpoint sits on the context block so
    # follow-up questions within the same project hit the cache.
    content_blocks: list[dict[str, Any]] = []
    if project_context is not None:
        context_json = json.dumps(project_context, sort_keys=True, default=str)
        content_blocks.append(
            {
                "type": "text",
                "text": f"<project_context>\n{context_json}\n</project_context>",
                "cache_control": {"type": "ephemeral"},
            }
        )
    content_blocks.append({"type": "text", "text": user_message})

    system_blocks = [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    message = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": content_blocks}],
    )

    text = _text_from(message)
    usage = _extract_usage(message)
    _log_cost(feature, model, usage, user_id)

    if expect_json:
        text = _strip_json_fence(text)

    return text, usage


def call_json(
    *,
    feature: str,
    user_message: str,
    project_context: dict[str, Any] | None = None,
    user_id: int | None = None,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    text, _ = call(
        feature=feature,
        user_message=user_message,
        project_context=project_context,
        user_id=user_id,
        max_tokens=max_tokens,
        expect_json=True,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("claude %s returned non-JSON: %s", feature, text[:500])
        raise ValueError(f"Claude returned invalid JSON for {feature}: {e}") from e


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # Drop opening fence line, optional language tag, and trailing fence.
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def stream(
    *,
    feature: str,
    user_message: str,
    project_context: dict[str, Any] | None = None,
    user_id: int | None = None,
    max_tokens: int = 2000,
) -> AsyncIterator[str]:
    """Async generator of text deltas, for SSE streaming to the browser."""
    system_prompt = SYSTEM_BY_FEATURE[feature]
    model = _model_for(feature)

    content_blocks: list[dict[str, Any]] = []
    if project_context is not None:
        context_json = json.dumps(project_context, sort_keys=True, default=str)
        content_blocks.append(
            {
                "type": "text",
                "text": f"<project_context>\n{context_json}\n</project_context>",
                "cache_control": {"type": "ephemeral"},
            }
        )
    content_blocks.append({"type": "text", "text": user_message})

    system_blocks = [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]

    client = _get_client()

    async def _gen():
        usage: dict[str, int] = {}
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": content_blocks}],
        ) as s:
            for text in s.text_stream:
                yield text
            final = s.get_final_message()
            usage = _extract_usage(final)
        _log_cost(feature, model, usage, user_id)

    return _gen()
