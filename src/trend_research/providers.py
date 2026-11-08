"""Explicit, single-attempt model transports; credentials never enter records.

The OpenAI-compatible thinking option is the ``chat_template_kwargs`` extension
used by llama.cpp and compatible templates. Leave it unset for servers/models
that do not implement that extension; it is a request, not proof of activation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


class ProviderError(RuntimeError):
    """A sanitized configuration, connection, or response error."""


def _failure_metadata(exc):
    """Diagnostic identifiers only; never exception messages or response bodies."""
    name = type(exc).__name__
    safe_type = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,79}", name) else "Exception"
    status = getattr(exc, "status_code", None)
    return f" ({safe_type}, HTTP {status})" if type(status) is int and 100 <= status <= 599 else f" ({safe_type})"


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _text(value, *, required=False):
    return (isinstance(value, str) and len(value) <= 1024
            and value == value.strip() and not any(ord(c) < 32 for c in value)
            and (bool(value) or not required))


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str = ""
    api_key_env: str = ""
    max_tokens: int = 2048
    temperature: float | None = 0.2
    timeout_seconds: float = 120
    checkpoint_label: str = "base"
    model_revision: str = ""
    quantization: str = ""
    input_price_per_million: float | None = None
    output_price_per_million: float | None = None
    enable_thinking: bool | None = None
    effort: str | None = None

    def __post_init__(self):
        if self.provider not in ("anthropic", "openai_compatible", "demo"):
            raise ProviderError("지원하지 않는 모델 제공자입니다.")
        if not _text(self.model, required=True):
            raise ProviderError("모델 식별자를 확인하세요.")
        for name in ("checkpoint_label", "model_revision", "quantization"):
            if not _text(getattr(self, name), required=name == "checkpoint_label"):
                raise ProviderError("모델 실행 식별 설정을 확인하세요.")
        if not _text(self.api_key_env) or (self.api_key_env and not re.fullmatch(
                r"[A-Z_][A-Z0-9_]*", self.api_key_env)):
            raise ProviderError("API 키 값 대신 환경 변수 이름을 설정하세요.")
        if not _text(self.base_url):
            raise ProviderError("모델 서버 주소를 확인하세요.")
        if self.base_url:
            try:
                parsed = urlsplit(self.base_url)
                valid = (parsed.scheme in ("http", "https") and parsed.hostname
                         and not parsed.username and not parsed.password
                         and not parsed.query and not parsed.fragment
                         and not any(c.isspace() for c in self.base_url))
                parsed.port  # Validate the port without echoing the URL.
            except ValueError:
                valid = False
            if not valid:
                raise ProviderError("서버 주소에는 인증정보·쿼리·프래그먼트를 넣을 수 없습니다.")
        if self.provider == "openai_compatible" and not self.base_url:
            raise ProviderError("OpenAI 호환 서버의 base_url을 지정하세요.")
        if self.provider == "anthropic" and self.base_url.rstrip("/") not in (
                "", "https://api.anthropic.com"):
            raise ProviderError("Anthropic 연결은 공식 API 주소만 지원합니다.")
        if self.provider == "demo" and (self.base_url or self.api_key_env):
            raise ProviderError("데모 설정에는 서버나 인증정보를 지정할 수 없습니다.")
        if type(self.max_tokens) is not int or self.max_tokens <= 0:
            raise ProviderError("max_tokens는 양의 정수여야 합니다.")
        if self.temperature is not None and (
                not _number(self.temperature) or not 0 <= self.temperature <= 2):
            raise ProviderError("temperature는 0 이상 2 이하의 수치 또는 null이어야 합니다.")
        if self.provider == "anthropic" and self.temperature is not None:
            raise ProviderError("현재 Anthropic SDK는 temperature를 지원하지 않습니다. null로 설정하세요.")
        if not _number(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ProviderError("timeout_seconds는 양의 수치여야 합니다.")
        for name in ("input_price_per_million", "output_price_per_million"):
            value = getattr(self, name)
            if value is not None and (not _number(value) or value < 0):
                raise ProviderError("토큰 단가는 0 이상의 수치 또는 null이어야 합니다.")
        if self.enable_thinking is not None and type(self.enable_thinking) is not bool:
            raise ProviderError("enable_thinking은 true, false, null만 지원합니다.")
        if self.provider != "openai_compatible" and self.enable_thinking is not None:
            raise ProviderError("이 제공자는 enable_thinking 확장 설정을 지원하지 않습니다.")
        if self.effort is not None and (self.provider != "anthropic" or self.effort not in ("low", "medium", "high")):
            raise ProviderError("effort는 Anthropic의 low, medium, high만 지원합니다.")

    def public_dict(self):
        """Return only validated configuration, never resolved credentials."""
        return asdict(self)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(_):
    raise ValueError("non-finite JSON number")


def load_configs(path):
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
        if len(content) > 65536:
            raise ValueError("oversized configuration")
        data = json.loads(content, object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
        if not isinstance(data, dict) or set(data) != {"local", "frontier"}:
            raise ValueError("invalid pipeline mapping")
        names = {field.name for field in fields(ModelConfig)}
        result = {}
        for pipeline in ("local", "frontier"):
            settings = data[pipeline]
            if not isinstance(settings, dict) or set(settings) - names:
                raise ValueError("unsupported configuration field")
            result[pipeline] = ModelConfig(**settings)
        return result
    except ProviderError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        raise ProviderError("모델 설정 파일의 형식·필수 항목·지원 필드를 확인하세요.") from None


def _credentials(root, names):
    """Read only explicitly named variables; dotenv contents are never executed."""
    names = {name for name in names if name}
    if not names:
        return {}
    values = {}
    path = Path(root) / ".env"
    try:
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key not in names:
                    continue
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key] = value
        for name in names:
            if name in os.environ:
                values[name] = os.environ[name].strip()
    except (OSError, UnicodeError):
        raise ProviderError("모델 인증 설정을 읽을 수 없습니다.") from None
    if any("\n" in value or "\r" in value for value in values.values()):
        raise ProviderError("모델 인증 설정의 형식이 올바르지 않습니다.")
    return values


def _mapping(value):
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        data = value.model_dump(exclude_none=True)
        return data if isinstance(data, dict) else {}
    return {}


def _token_count(value):
    return type(value) is int and value >= 0


def _usage(raw, provider):
    raw = _mapping(raw)
    names = (("input_tokens", "output_tokens") if provider == "anthropic"
             else ("prompt_tokens", "completion_tokens"))
    result = {}
    for target, source in zip(("input_tokens", "output_tokens"), names):
        if _token_count(raw.get(source)):
            result[target] = raw[source]
    complete = "input_tokens" in result and "output_tokens" in result
    if provider == "anthropic":
        for name in ("cache_read_input_tokens", "cache_creation_input_tokens"):
            if name in raw:
                if _token_count(raw[name]):
                    result[name] = raw[name]
                    if "input_tokens" in result:
                        result["input_tokens"] += raw[name]
                else:
                    complete = False
        details = _mapping(raw.get("output_tokens_details"))
        reasoning = details.get("thinking_tokens")
    else:
        details = _mapping(raw.get("completion_tokens_details"))
        reasoning = details.get("reasoning_tokens")
    if _token_count(reasoning):
        result["reasoning_tokens"] = reasoning
    # Reasoning tokens are already included in output_tokens, never added again.
    return result, complete


def _final_text(text, finish_reason):
    """Discard leading textual reasoning, including an unfinished think block."""
    if not isinstance(text, str):
        raise ProviderError("모델 응답의 최종 텍스트 형식이 올바르지 않습니다.")
    final = text.strip()
    while re.match(r"^<think\s*>", final, flags=re.IGNORECASE):
        closing = re.search(r"</think\s*>", final, flags=re.IGNORECASE)
        if closing is None:
            return "", "incomplete_thinking"
        final = final[closing.end():].strip()
    # Some templates prefill <think> and only return its closing delimiter.
    if not final.startswith(("{", "[", "```")):
        closing = re.search(r"</think\s*>", final, flags=re.IGNORECASE)
        if closing:
            final = final[closing.end():].strip()
    if not final:
        return "", "missing_final"
    return final, finish_reason


def _response(text, actual_model, finish_reason, raw_usage, provider):
    if not _text(actual_model, required=True):
        raise ProviderError("모델 응답에 유효한 실행 모델 식별자가 없습니다.")
    if finish_reason is not None and not _text(finish_reason, required=True):
        raise ProviderError("모델 응답의 완료 상태 형식이 올바르지 않습니다.")
    text, finish_reason = _final_text(text, finish_reason)
    usage, complete = _usage(raw_usage, provider)
    return {"text": text, "actual_model": actual_model,
            "finish_reason": finish_reason, "usage": usage,
            "usage_complete": complete}


class ClaudeClient:
    """Official Anthropic SDK, without retries or inferred thinking settings."""

    def __init__(self, config, root, *, sdk_client=None):
        self.config = config
        self._owns_client = sdk_client is None
        if sdk_client is not None:
            self.client = sdk_client
            return
        name = config.api_key_env or "ANTHROPIC_API_KEY"
        settings = _credentials(root, (name, "ANTHROPIC_WORKSPACE_ID"))
        if not settings.get(name):
            raise ProviderError("Anthropic API 키 환경 변수를 설정하세요.")
        try:
            import anthropic
            headers = {}
            if settings.get("ANTHROPIC_WORKSPACE_ID"):
                headers["anthropic-workspace-id"] = settings["ANTHROPIC_WORKSPACE_ID"]
            self.client = anthropic.Anthropic(
                api_key=settings[name], base_url="https://api.anthropic.com",
                default_headers=headers, max_retries=0, timeout=config.timeout_seconds,
            )
        except ImportError:
            raise ProviderError("Anthropic SDK 의존성을 설치하세요.") from None
        except Exception:
            raise ProviderError("Anthropic 연결을 초기화할 수 없습니다.") from None

    def generate(self, system, user):
        try:
            options = {"output_config": {"effort": self.config.effort}} if self.config.effort else {}
            message = self.client.messages.create(
                model=self.config.model, max_tokens=self.config.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                **options,
            )
            data = _mapping(message)
            blocks = data.get("content")
            if not isinstance(blocks, list):
                raise ProviderError("Anthropic 응답 형식이 올바르지 않습니다.")
            texts = []
            for block in blocks:
                block = _mapping(block)
                if block.get("type") == "text":
                    if not isinstance(block.get("text"), str):
                        raise ProviderError("Anthropic 최종 텍스트 형식이 올바르지 않습니다.")
                    texts.append(block["text"])
            return _response("\n\n".join(texts), data.get("model"),
                             data.get("stop_reason"), data.get("usage"), "anthropic")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("Anthropic 요청에 실패했습니다." + _failure_metadata(exc)) from None

    def close(self):
        if self._owns_client:
            self.client.close()


class OpenAICompatibleClient:
    """One JSON HTTP request to Ollama, llama.cpp, LM Studio, or a compatible API."""

    def __init__(self, config, root, *, session=None):
        self.config = config
        self._owns_session = session is None
        settings = _credentials(root, (config.api_key_env,))
        self._headers = {"Content-Type": "application/json"}
        if config.api_key_env:
            if not settings.get(config.api_key_env):
                raise ProviderError("지정한 API 키 환경 변수를 설정하세요.")
            self._headers["Authorization"] = "Bearer " + settings[config.api_key_env]
        if session is not None:
            self.session = session
            return
        try:
            import requests
            self.session = requests.Session()
            # Avoid implicit .netrc credentials, environment proxying and retries.
            self.session.trust_env = False
            self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries=0))
            self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
        except ImportError:
            raise ProviderError("requests 의존성을 설치하세요.") from None
        except Exception:
            raise ProviderError("모델 서버 연결을 초기화할 수 없습니다.") from None

    def generate(self, system, user):
        payload = {
            "model": self.config.model, "max_tokens": self.config.max_tokens,
            "stream": False,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.enable_thinking is not None:
            payload["chat_template_kwargs"] = {"enable_thinking": self.config.enable_thinking}
        try:
            response = self.session.post(
                self.config.base_url.rstrip("/") + "/chat/completions",
                json=payload, headers=self._headers,
                timeout=(min(15, self.config.timeout_seconds), self.config.timeout_seconds),
                allow_redirects=False,
            )
            try:
                if not 200 <= response.status_code < 300:
                    status = response.status_code
                    safe_status = str(status) if type(status) is int and 100 <= status <= 599 else "unknown"
                    raise ProviderError("모델 서버가 요청을 거부했습니다. HTTP " + safe_status)
                data = response.json()
            finally:
                response.close()
            if not isinstance(data, dict) or data.get("error") is not None:
                raise ProviderError("모델 서버 응답 형식이 올바르지 않습니다.")
            choices = data.get("choices")
            if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                raise ProviderError("모델 서버의 응답 선택 형식이 올바르지 않습니다.")
            choice = choices[0]
            message = choice.get("message")
            if not isinstance(message, dict):
                raise ProviderError("모델 서버의 메시지 형식이 올바르지 않습니다.")
            # Never copy reasoning_content/thinking or tool-call arguments.
            content = message.get("content")
            if content is None:
                content = ""
            return _response(content, data.get("model"), choice.get("finish_reason"),
                             data.get("usage"), "openai_compatible")
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("모델 서버 요청에 실패했습니다." + _failure_metadata(exc)) from None

    def close(self):
        if self._owns_session:
            self.session.close()


def create_client(config, root):
    if not isinstance(config, ModelConfig):
        raise ProviderError("검증된 ModelConfig 설정이 필요합니다.")
    if config.provider == "anthropic":
        return ClaudeClient(config, root)
    if config.provider == "openai_compatible":
        return OpenAICompatibleClient(config, root)
    raise ProviderError("데모 클라이언트는 명시적인 데모 실행에서만 사용할 수 있습니다.")
