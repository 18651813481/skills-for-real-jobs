#!/usr/bin/env python3
"""Detect the slide-maker Image2 route from the current Codex login mode."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping


ALLOWED_ROUTES = {"codex_builtin_imagegen", "tokenlane_image2"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_image_route(
    requested_route: str = "auto",
    *,
    auth_path: Path | None = None,
    config_path: Path | None = None,
    image2_key_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return route detection details.

    ChatGPT/Codex membership mode always resolves to built-in image_gen, even
    when auth.json contains an OPENAI_API_KEY field. Explicit non-auto route
    arguments still win because they are intentional operator choices.
    """

    if requested_route in ALLOWED_ROUTES:
        return {
            "requested_route": requested_route,
            "image_route": requested_route,
            "reason": "explicit_route",
        }
    if requested_route != "auto":
        raise SystemExit(f"invalid image route: {requested_route}")

    env_map = env if env is not None else os.environ
    home = Path.home()
    auth = auth_path or home / ".codex" / "auth.json"
    config = config_path or home / ".codex" / "config.toml"
    image2_key = image2_key_path or home / ".codex" / "Image2" / "api_key"

    auth_data = _read_json(auth)
    auth_mode = str(auth_data.get("auth_mode") or "").strip().lower()
    config_text = _read_text(config)
    has_tokenlane_env = bool(
        str(env_map.get("TOKENLANE_API_KEY") or "").strip()
        or str(env_map.get("IMAGE2_API_KEY") or "").strip()
    )
    has_openai_env = bool(str(env_map.get("OPENAI_API_KEY") or "").strip())
    has_tokenlane_config = "api.tokenlane.tech" in config_text
    has_image2_key_file = image2_key.exists() and bool(_read_text(image2_key).strip())

    if auth_mode == "chatgpt":
        return {
            "requested_route": "auto",
            "image_route": "codex_builtin_imagegen",
            "reason": "chatgpt_membership",
            "auth_mode": auth_mode,
            "auth_path": str(auth),
            "config_path": str(config),
            "has_openai_key_field_in_auth": "OPENAI_API_KEY" in auth_data,
            "has_tokenlane_env": has_tokenlane_env,
            "has_tokenlane_config": has_tokenlane_config,
            "has_image2_key_file": has_image2_key_file,
        }

    if auth_mode and auth_mode != "chatgpt":
        reason = f"non_membership_auth_mode:{auth_mode}"
        route = "tokenlane_image2"
    elif has_tokenlane_env or has_openai_env or has_tokenlane_config or has_image2_key_file:
        reason = "api_or_tokenlane_configuration"
        route = "tokenlane_image2"
    else:
        reason = "no_api_route_detected"
        route = "codex_builtin_imagegen"

    return {
        "requested_route": "auto",
        "image_route": route,
        "reason": reason,
        "auth_mode": auth_mode,
        "auth_path": str(auth),
        "config_path": str(config),
        "has_openai_env": has_openai_env,
        "has_tokenlane_env": has_tokenlane_env,
        "has_tokenlane_config": has_tokenlane_config,
        "has_image2_key_file": has_image2_key_file,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect slide-maker Image2 route.")
    parser.add_argument("--route", default="auto", choices=sorted(ALLOWED_ROUTES | {"auto"}))
    parser.add_argument("--auth-json", help="Defaults to ~/.codex/auth.json.")
    parser.add_argument("--config-toml", help="Defaults to ~/.codex/config.toml.")
    parser.add_argument("--image2-key", help="Defaults to ~/.codex/Image2/api_key.")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = detect_image_route(
        args.route,
        auth_path=Path(args.auth_json).expanduser().resolve() if args.auth_json else None,
        config_path=Path(args.config_toml).expanduser().resolve() if args.config_toml else None,
        image2_key_path=Path(args.image2_key).expanduser().resolve() if args.image2_key else None,
    )
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["image_route"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
