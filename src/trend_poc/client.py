"""Standalone Claude transport for the monthly PoC; no automatic API retries."""
import copy
import math
import os
from pathlib import Path

MODEL = "claude-opus-5-5"


class VerificationAIError(RuntimeError):
    """A review stopped; saved attempts can be inspected before explicit retry."""


class IncompleteResponse(VerificationAIError):
    pass


def _settings(root):
    """Read literal settings only; never execute or return other .env entries."""
    values = {}
    path = Path(root) / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() not in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID"):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID"):
        if key in os.environ:
            values[key] = os.environ[key].strip()
    return values


def _usage(values):
    """Keep numeric API accounting fields, never content or thinking text."""
    result = {}
    for key, value in (values or {}).items():
        if isinstance(value, dict):
            nested = _usage(value)
            if nested:
                result[key] = nested
        elif "token" in key and isinstance(value, (int, float)) and not isinstance(value, bool):
            if math.isfinite(value) and value >= 0:
                result[key] = value
    return result


class ClaudeClient:
    """Official SDK transport with no automatic retry or model substitution."""

    def __init__(self, root=None):
        try:
            import anthropic
            import httpx2
        except ImportError:
            raise VerificationAIError("Anthropic SDK와 httpx2 의존성이 필요합니다.") from None
        values = _settings(root or Path(__file__).resolve().parents[2])
        if not values.get("ANTHROPIC_API_KEY"):
            raise VerificationAIError("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        headers = {}
        if values.get("ANTHROPIC_WORKSPACE_ID"):
            headers["anthropic-workspace-id"] = values["ANTHROPIC_WORKSPACE_ID"]
        self.client = anthropic.Anthropic(
            api_key=values["ANTHROPIC_API_KEY"],
            base_url="https://api.anthropic.com",
            default_headers=headers,
            max_retries=0,
            timeout=httpx2.Timeout(120.0, connect=15.0),
        )

    def close(self):
        self.client.close()

    def count(self, payload):
        return self.client.messages.count_tokens(
            model=payload["model"], system=payload["system"], messages=payload["messages"]
        ).input_tokens

    def generate(self, payload, checkpoint):
        text_parts, usage = {}, {}
        message_id = actual_model = stop_reason = None
        ended = False
        usage_complete = False
        with self.client.messages.stream(**payload) as stream:
            for event in stream:
                if event.type == "message_start":
                    usage.update(_usage(event.message.usage.model_dump(exclude_none=True)))
                    message_id, actual_model = event.message.id, event.message.model
                elif event.type == "content_block_start" and event.content_block.type == "text":
                    text_parts[event.index] = event.content_block.text
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    text_parts[event.index] = text_parts.get(event.index, "") + event.delta.text
                elif event.type == "message_delta":
                    usage.update(_usage(event.usage.model_dump(exclude_none=True)))
                    stop_reason = event.delta.stop_reason
                    usage_complete = stop_reason is not None
                elif event.type == "message_stop":
                    ended = True
                elif event.type == "error":
                    raise IncompleteResponse("응답 스트림이 오류로 중단됐습니다.")
                else:
                    continue
                checkpoint({
                    "text": "\n\n".join(text_parts[k] for k in sorted(text_parts)),
                    "usage": copy.deepcopy(usage), "message_id": message_id,
                    "actual_model": actual_model, "stop_reason": stop_reason,
                    "usage_complete": usage_complete,
                })
            if not ended:
                raise IncompleteResponse("응답 스트림에 완료 표시가 없습니다.")
            message = stream.get_final_message()
        return {
            "text": "\n\n".join(block.text for block in message.content if block.type == "text"),
            "usage": _usage(message.usage.model_dump(exclude_none=True)),
            "message_id": message.id, "actual_model": message.model,
            "stop_reason": message.stop_reason,
            "usage_complete": True,
        }
