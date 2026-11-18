"""Bounded, secret-safe proof of a real Zhipu tool-call round trip.

This is deliberately separate from the application workflow. The function is real;
the sensor values it returns are explicitly fictional fixtures. Nothing runs on
import, and the key is never written into the result file or console output.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-5.3-flash"
LOCATION_ID = "training-floor-2"
TOOL_NAME = "query_sensor_data"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ProbeError(Exception):
    """Only locally authored messages may be passed to this exception."""

    def __init__(
        self, category: str, message: str, exit_code: int = 5,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.safe_message = message
        self.exit_code = exit_code
        self.http_status = http_status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_base_url(value: str) -> str:
    """The key may only be transmitted to this approved standard API endpoint."""
    try:
        parsed = urllib.parse.urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname == "open.bigmodel.cn"
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and parsed.path.rstrip("/") == "/api/paas/v4"
            and not parsed.query
            and not parsed.fragment
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ProbeError(
            "invalid_endpoint",
            "仅允许智谱官方标准 HTTPS API 地址；其他服务商须另行适配。",
            2,
        )
    return DEFAULT_BASE_URL


def validate_model(value: str) -> str:
    # Prevent arbitrary text/control characters from reaching metadata or logs.
    if (
        not isinstance(value, str) or not 1 <= len(value) <= 80
        or not value.startswith("glm-")
        or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for ch in value)
    ):
        raise ProbeError("invalid_model", "模型名称格式无效。", 2)
    return value


def read_key(path: Path) -> str:
    try:
        # A size guard avoids accidentally reading an unrelated large document.
        if path.stat().st_size > 4096:
            raise ProbeError("invalid_key_file", "密钥文件不是预期的纯文本格式。", 2)
        key = path.read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeError):
        raise ProbeError("key_unreadable", "无法读取 UTF-8 密钥文件。", 2) from None
    if not 16 <= len(key) <= 1024 or not key.isascii() or any(c.isspace() for c in key):
        raise ProbeError("invalid_key_file", "密钥文件须仅包含单个有效格式的密钥。", 2)
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        # Never forward Authorization across a redirect, even on the same host.
        return None


def request_json(url: str, key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TianqiongDemo-IsolatedProbe/0.1",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ProbeError("oversized_response", "模型响应超出探针大小限制。", 4)
        result = json.loads(body.decode("utf-8"))
        if not isinstance(result, dict):
            raise ProbeError("invalid_response", "模型响应不是有效的 JSON 对象。")
        return result
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        if status in (401, 403):
            raise ProbeError(
                "authentication_or_permission", "鉴权或权限校验失败，请检查 Key 类型与模型权限。", 3, status,
            ) from None
        if status in (402, 429):
            raise ProbeError(
                "quota_or_rate_limit", "额度不足或触发限流；探针未自动重试。", 4, status,
            ) from None
        if 300 <= status < 400:
            raise ProbeError("redirect_refused", "服务要求重定向；为保护密钥已停止。", 4, status) from None
        raise ProbeError(
            "http_error", "模型请求被拒绝，请核对模型可用性与请求参数。", 4, status,
        ) from None
    except (TimeoutError, socket.timeout):
        raise ProbeError("timeout", "模型请求超时；未自动重试，已产生用量仍可能计费。", 4) from None
    except urllib.error.URLError:
        raise ProbeError("network_error", "无法建立可信 HTTPS 连接，请检查网络或代理。", 4) from None
    except (json.JSONDecodeError, UnicodeError):
        raise ProbeError("invalid_response", "模型响应无法解析为 UTF-8 JSON。") from None
    except ssl.SSLError:
        raise ProbeError("tls_error", "HTTPS 证书或加密连接校验失败。", 4) from None


def get_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProbeError("missing_choice", "模型没有返回可验证的候选结果。")
    if choices[0].get("finish_reason") == "length":
        raise ProbeError("token_limit", "响应达到本次 Token 上限，未自动增加预算或重试。")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ProbeError("missing_message", "模型响应缺少消息对象。")
    return message


def safe_usage(response: dict[str, Any]) -> dict[str, int]:
    raw = response.get("usage")
    if not isinstance(raw, dict):
        return {}
    return {
        name: raw[name]
        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        if type(raw.get(name)) is int and 0 <= raw[name] <= 100_000_000
    }


def execute_tool(message: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise ProbeError("missing_tool_call", "模型未返回恰好一次可执行的 tool_calls，不能认定工具调用成功。")
    call = calls[0]
    if not isinstance(call, dict) or call.get("type") != "function":
        raise ProbeError("invalid_tool_call", "模型返回的工具调用类型无效。")
    function = call.get("function")
    call_id = call.get("id")
    if not isinstance(call_id, str) or not call_id or len(call_id) > 256:
        raise ProbeError("invalid_tool_call", "工具调用缺少有效标识。")
    if not isinstance(function, dict) or function.get("name") != TOOL_NAME:
        raise ProbeError("unknown_tool", "模型请求了未登记的工具，已拒绝执行。")
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (ValueError, TypeError):
        raise ProbeError("invalid_arguments", "工具参数不是有效的 JSON。") from None
    if arguments != {"location_id": LOCATION_ID}:
        raise ProbeError("invalid_arguments", "工具参数未通过地点与字段校验，已拒绝执行。")
    return call_id, query_sensor_data(**arguments)


def query_sensor_data(location_id: str) -> dict[str, Any]:
    """A real local read-only function over an explicitly fictional fixture."""
    if location_id != LOCATION_ID:
        raise ProbeError("unknown_location", "演示地点不存在。")
    return {
        "location_id": LOCATION_ID,
        "temperature_c": 78,
        "smoke_alert": True,
        "is_simulated": True,
        "source": "isolated_probe_fixture",
        "note": "仅为接口协议验证数据，不是实时监测或消防判定。",
    }


def validate_final(message: dict[str, Any]) -> None:
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ProbeError("empty_final", "工具回传后未得到模型最终内容。")
    if message.get("tool_calls"):
        raise ProbeError("unexpected_tool_call", "工具回传后模型仍请求额外调用，本次探针已停止。")
    try:
        result = json.loads(content)
    except (ValueError, TypeError):
        raise ProbeError("invalid_final_json", "模型最终内容未满足结构化 JSON 要求。") from None
    if not isinstance(result, dict) or not (
        result.get("location_id") == LOCATION_ID
        and type(result.get("temperature_c")) in (int, float)
        and result.get("temperature_c") == 78
        and result.get("smoke_alert") is True
        and result.get("is_simulated") is True
    ):
        raise ProbeError("ungrounded_final", "模型最终内容与已执行工具的模拟事实不一致。")


def probe(
    key_file: Path,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    timeout: int = 60,
    max_tokens: int = 1536,
    transport: Callable[..., dict[str, Any]] = request_json,
) -> tuple[dict[str, Any], int]:
    started = time.monotonic()
    metadata: dict[str, Any] = {
        "provider": "zhipu",
        "model": DEFAULT_MODEL,
        "scope": "isolated_tool_probe",
        "configured": False,
        "verified": False,
        "status": "failed",
        "started_at": utc_now(),
        "request_count": 0,
        "usage": [],
        "tool_name": None,
        "tool_executed": False,
    }
    exit_code = 5
    try:
        base_url = validate_base_url(base_url)
        model = validate_model(model)
        metadata["model"] = model
        if not 1 <= timeout <= 60 or not 256 <= max_tokens <= 4096:
            raise ProbeError("invalid_limits", "超时须在 1–60 秒、Token 上限须在 256–4096 之间。", 2)
        key = read_key(key_file)
        metadata["configured"] = True
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "你在进行一次独立接口验证，不是应急处置。先调用提供的查询工具获取数据。"
                "不可编造数值，也不可把模拟数据描述为实测数据。只调用一次工具。",
            },
            {"role": "user", "content": f"请调用 query_sensor_data 查询 location_id={LOCATION_ID} 的模拟监测数据。"},
        ]
        tool = {
            "type": "function",
            "function": {
                "name": TOOL_NAME,
                "description": "查询独立探针中虚构实训楼二层的模拟传感器数据；不连接真实设备。",
                "parameters": {
                    "type": "object",
                    "properties": {"location_id": {"type": "string", "enum": [LOCATION_ID]}},
                    "required": ["location_id"],
                    "additionalProperties": False,
                },
            },
        }
        common: dict[str, Any] = {"model": model, "stream": False, "max_tokens": max_tokens}
        metadata["request_count"] += 1
        first = transport(
            base_url + "/chat/completions", key,
            {**common, "messages": messages, "tools": [tool], "tool_choice": "auto"}, timeout,
        )
        metadata["usage"].append(safe_usage(first))
        assistant = get_message(first)
        call_id, tool_result = execute_tool(assistant)
        metadata["tool_name"] = TOOL_NAME
        metadata["tool_executed"] = True
        # Preserve provider-required reasoning only in this in-memory protocol
        # message. It is never copied to metadata, logs, files, or the web app.
        assistant_for_protocol = {
            k: assistant[k]
            for k in ("content", "tool_calls", "reasoning_content") if k in assistant
        }
        assistant_for_protocol["role"] = "assistant"
        messages.extend([
            assistant_for_protocol,
            {"role": "tool", "tool_call_id": call_id, "content": json.dumps(tool_result, ensure_ascii=False)},
            {
                "role": "user",
                "content": "根据刚才的工具返回，只输出 JSON 对象，字段严格为 location_id、temperature_c、"
                "smoke_alert、is_simulated。值必须来自工具返回，不添加风险结论或其他文字。",
            },
        ])
        metadata["request_count"] += 1
        second = transport(
            base_url + "/chat/completions", key,
            {**common, "messages": messages, "response_format": {"type": "json_object"}}, timeout,
        )
        metadata["usage"].append(safe_usage(second))
        validate_final(get_message(second))
        metadata.update({
            "verified": True,
            "status": "verified",
            "message": "真实模型工具调用及结果回传验证通过；仅为独立模拟数据探针，应用工作流尚未验证。",
            "tool_result_summary": {
                "location_id": LOCATION_ID, "temperature_c": 78,
                "smoke_alert": True, "is_simulated": True,
            },
            "error_category": None,
        })
        exit_code = 0
    except ProbeError as exc:
        metadata.update({"error_category": exc.category, "message": exc.safe_message})
        if exc.http_status is not None:
            metadata["http_status"] = exc.http_status
        exit_code = exc.exit_code
    except Exception:
        # Exceptions from HTTP libraries may include response bodies or headers.
        # Deliberately do not print a traceback, repr, or the original message.
        metadata.update({"error_category": "internal_error", "message": "探针内部校验失败；未输出可能包含敏感信息的异常详情。"})
        exit_code = 5
    metadata["finished_at"] = utc_now()
    metadata["duration_ms"] = round((time.monotonic() - started) * 1000)
    return metadata, exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="最多两次请求的独立智谱工具调用验证，不会自动切换模型。")
    parser.add_argument("--key-file", required=True, type=Path, help="仅传文件路径，禁止在参数中传密钥。")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output", type=Path, default=Path(".runtime/model_probe.json"))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=1536)
    args = parser.parse_args()
    metadata, code = probe(args.key_file, args.model, args.base_url, args.timeout, args.max_tokens)
    try:
        # Prevent overwriting the credential file even after a mistyped command.
        if args.output.resolve() == args.key_file.resolve():
            print("Probe output path must not equal the key path.", file=sys.stderr)
            return 6
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + ".tmp")
        if temporary.resolve() == args.key_file.resolve():
            print("Probe temporary path must not equal the key path.", file=sys.stderr)
            return 6
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)
    except OSError:
        print("Probe result could not be saved; no sensitive error details were emitted.", file=sys.stderr)
        return 6
    # ASCII JSON is safe across the Windows terminal's possible legacy encodings.
    print(json.dumps(metadata, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
