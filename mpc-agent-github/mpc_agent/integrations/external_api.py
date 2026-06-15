from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


READ_METHODS = {"GET", "HEAD", "OPTIONS"}
ALLOWED_METHODS = READ_METHODS | {"POST", "PUT", "PATCH", "DELETE"}


@dataclass(frozen=True)
class ExternalSystem:
    name: str
    base_url: str
    description: str = ""
    allow_write: bool = False
    api_key_env: str = ""
    auth_scheme: str = "Bearer"
    timeout_seconds: int = 20
    default_headers: dict[str, str] = field(default_factory=dict)
    allowed_prefixes: list[str] = field(default_factory=list)


def _parse_system(item: dict[str, Any]) -> ExternalSystem:
    name = str(item.get("name", "")).strip()
    base_url = str(item.get("base_url", "")).strip()
    if not name or not base_url:
        raise ValueError("Each system requires `name` and `base_url`.")

    prefixes_raw = item.get("allowed_prefixes", [])
    prefixes = [str(x).strip() for x in prefixes_raw if str(x).strip()] if isinstance(prefixes_raw, list) else []

    return ExternalSystem(
        name=name,
        base_url=base_url.rstrip("/"),
        description=str(item.get("description", "")).strip(),
        allow_write=bool(item.get("allow_write", False)),
        api_key_env=str(item.get("api_key_env", "")).strip(),
        auth_scheme=str(item.get("auth_scheme", "Bearer")).strip(),
        timeout_seconds=int(item.get("timeout_seconds", 20)),
        default_headers={str(k): str(v) for k, v in dict(item.get("default_headers", {})).items()},
        allowed_prefixes=prefixes,
    )


def _load_systems() -> dict[str, ExternalSystem]:
    raw = os.getenv("EXTERNAL_SYSTEMS_JSON", "").strip()
    if not raw:
        return {}

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        systems_raw = parsed.get("systems", [])
    elif isinstance(parsed, list):
        systems_raw = parsed
    else:
        raise ValueError("EXTERNAL_SYSTEMS_JSON must be a list or object with `systems`.")

    systems: dict[str, ExternalSystem] = {}
    for item in systems_raw:
        if not isinstance(item, dict):
            continue
        system = _parse_system(item)
        systems[system.name] = system
    return systems


def list_external_systems() -> list[dict[str, Any]]:
    systems = _load_systems()
    rows: list[dict[str, Any]] = []
    for system in systems.values():
        has_api_key = bool(system.api_key_env and os.getenv(system.api_key_env, "").strip())
        rows.append(
            {
                "name": system.name,
                "base_url": system.base_url,
                "description": system.description,
                "allow_write": system.allow_write,
                "api_key_env": system.api_key_env,
                "api_key_present": has_api_key,
                "auth_scheme": system.auth_scheme,
                "timeout_seconds": system.timeout_seconds,
                "allowed_prefixes": list(system.allowed_prefixes),
            }
        )
    rows.sort(key=lambda row: str(row["name"]))
    return rows


def _build_url(system: ExternalSystem, path: str, query: dict[str, Any] | None) -> str:
    path_clean = path.strip()
    if path_clean.startswith("http://") or path_clean.startswith("https://"):
        raise ValueError("`path` must be relative, absolute URL is not allowed.")

    normalized = path_clean.lstrip("/")
    if system.allowed_prefixes:
        ok = any(normalized.startswith(prefix.lstrip("/")) for prefix in system.allowed_prefixes)
        if not ok:
            raise PermissionError(
                f"Path `{path}` is not in allowed_prefixes for system `{system.name}`."
            )

    url = urllib.parse.urljoin(f"{system.base_url}/", normalized)
    if query:
        params = {str(k): str(v) for k, v in query.items()}
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return url


def _auth_headers(system: ExternalSystem) -> dict[str, str]:
    if not system.api_key_env:
        return {}

    token = os.getenv(system.api_key_env, "").strip()
    if not token:
        raise ValueError(f"Missing API key in env `{system.api_key_env}`.")

    scheme = system.auth_scheme.strip()
    if not scheme:
        return {}

    lower = scheme.lower()
    if lower == "bearer":
        return {"Authorization": f"Bearer {token}"}
    if lower in {"x-api-key", "x_api_key"}:
        return {"X-API-Key": token}
    return {scheme: token}


def call_external_api(
    *,
    system_name: str,
    method: str = "GET",
    path: str = "",
    query: dict[str, Any] | None = None,
    headers: dict[str, Any] | None = None,
    body: Any = None,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    systems = _load_systems()
    system = systems.get(system_name)
    if system is None:
        raise KeyError(f"Unknown external system: {system_name}")

    method_upper = method.strip().upper() or "GET"
    if method_upper not in ALLOWED_METHODS:
        raise ValueError(f"Unsupported method: {method_upper}")
    if not system.allow_write and method_upper not in READ_METHODS:
        raise PermissionError(
            f"System `{system.name}` is read-only. `{method_upper}` is not allowed."
        )

    url = _build_url(system, path, query)

    request_headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "mpc-agent/1.0",
    }
    request_headers.update(system.default_headers)
    request_headers.update(_auth_headers(system))
    if headers:
        request_headers.update({str(k): str(v) for k, v in headers.items()})

    data: bytes | None = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            data = str(body).encode("utf-8")

    timeout = timeout_seconds if timeout_seconds is not None else system.timeout_seconds
    req = urllib.request.Request(url=url, data=data, headers=request_headers, method=method_upper)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace")
            content_type = resp.headers.get("Content-Type", "")
            parsed_json: Any | None = None
            if "application/json" in content_type.lower():
                try:
                    parsed_json = json.loads(text)
                except json.JSONDecodeError:
                    parsed_json = None
            return {
                "ok": True,
                "system": system.name,
                "method": method_upper,
                "url": url,
                "status": int(resp.status),
                "headers": dict(resp.headers.items()),
                "text": text,
                "json": parsed_json,
            }
    except urllib.error.HTTPError as error:
        body_text = error.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "system": system.name,
            "method": method_upper,
            "url": url,
            "status": int(error.code),
            "reason": str(error.reason),
            "text": body_text,
        }
    except urllib.error.URLError as error:
        return {
            "ok": False,
            "system": system.name,
            "method": method_upper,
            "url": url,
            "status": None,
            "reason": str(error.reason),
            "text": "",
        }
