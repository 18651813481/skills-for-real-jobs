#!/usr/bin/env python3
"""Generate images through Tokenlane and save returned b64_json files locally."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


TOKENLANE_ENDPOINT = "https://api.tokenlane.tech/v1/images/generations"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
MAX_COUNT = 4
IMAGE2_CONFIG_DIR = Path.home() / ".codex" / "Image2"

SIZE_ALIASES = {
    "": DEFAULT_SIZE,
    "default": DEFAULT_SIZE,
    "square": DEFAULT_SIZE,
    "1:1": DEFAULT_SIZE,
    "方图": DEFAULT_SIZE,
    "正方形": DEFAULT_SIZE,
    "1024x1024": DEFAULT_SIZE,
    "landscape": "1536x1024",
    "wide": "1536x1024",
    "horizontal": "1536x1024",
    "横图": "1536x1024",
    "宽图": "1536x1024",
    "16:9": "1536x1024",
    "3:2": "1536x1024",
    "1536x1024": "1536x1024",
    "portrait": "1024x1536",
    "vertical": "1024x1536",
    "poster": "1024x1536",
    "竖图": "1024x1536",
    "海报": "1024x1536",
    "2:3": "1024x1536",
    "1024x1536": "1024x1536",
    "auto": "auto",
}
SUPPORTED_SIZES = {"1024x1024", "1536x1024", "1024x1536", "auto"}


class TokenlaneImageError(RuntimeError):
    pass


def codex_config_uses_tokenlane() -> bool:
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        text = config_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return False
    return "api.tokenlane.tech" in text


def read_codex_auth_key() -> str:
    if not codex_config_uses_tokenlane():
        return ""

    auth_path = Path.home() / ".codex" / "auth.json"
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    key = payload.get("OPENAI_API_KEY")
    return key.strip() if isinstance(key, str) else ""


def read_image2_key_file() -> str:
    key_path = IMAGE2_CONFIG_DIR / "api_key"
    try:
        return key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def read_image2_config_key() -> str:
    config_path = IMAGE2_CONFIG_DIR / "config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    key = payload.get("api_key")
    return key.strip() if isinstance(key, str) else ""


def resolve_api_key() -> str:
    env_key = os.environ.get("TOKENLANE_API_KEY", "").strip()
    if env_key:
        return env_key
    image2_env_key = os.environ.get("IMAGE2_API_KEY", "").strip()
    if image2_env_key:
        return image2_env_key
    file_key = read_image2_key_file()
    if file_key:
        return file_key
    config_key = read_image2_config_key()
    if config_key:
        return config_key
    return read_codex_auth_key()


def normalize_model(model: str) -> tuple[str, str]:
    raw = (model or DEFAULT_MODEL).strip()
    if raw and raw != DEFAULT_MODEL:
        return DEFAULT_MODEL, f"{raw} was ignored; Image2 always uses gpt-image-2"
    return DEFAULT_MODEL, ""


def normalize_size(size: str) -> str:
    key = re.sub(r"\s+", "", (size or "").strip().lower())
    normalized = SIZE_ALIASES.get(key)
    if normalized:
        return normalized
    if key in SUPPORTED_SIZES:
        return key
    allowed = ", ".join(sorted(SUPPORTED_SIZES))
    raise TokenlaneImageError(f"Unsupported image size {size!r}. Use one of: {allowed}.")


def validate_prompt(prompt: str) -> str:
    prompt = (prompt or "").strip()
    if not prompt:
        raise TokenlaneImageError("Image prompt is required.")
    return prompt


def validate_count(count: int) -> int:
    if count < 1 or count > MAX_COUNT:
        raise TokenlaneImageError(f"--count must be between 1 and {MAX_COUNT}.")
    return count


def validate_timeout(timeout: int) -> int:
    if timeout < 1:
        raise TokenlaneImageError("--timeout must be greater than 0.")
    return timeout


def decode_b64_image(raw: str) -> bytes:
    value = raw.strip()
    if "," in value and value.lower().startswith("data:image/"):
        value = value.split(",", 1)[1]
    value = "".join(value.split())
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TokenlaneImageError("Tokenlane Images API returned invalid image Base64.") from exc


def image_extension(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def redact_sensitive(text: str) -> str:
    text = re.sub(r"(?i)authorization:\s*bearer\s+\S+", "Authorization: Bearer [redacted]", text)
    text = re.sub(r"(?i)bearer\s+sk-[A-Za-z0-9._-]+", "Bearer [redacted]", text)
    return text


def parse_error_body(body: bytes) -> str:
    text = redact_sensitive(body.decode("utf-8", errors="replace").strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text[:500]
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return redact_sensitive(message)[:500]
    message = payload.get("message")
    return redact_sensitive(message)[:500] if isinstance(message, str) else text[:500]


def friendly_http_error(status_code: int, detail: str) -> str:
    detail = detail.strip()
    if status_code == 401:
        prefix = "Tokenlane rejected the API key. Check ~/.codex/Image2/api_key or TOKENLANE_API_KEY."
    elif status_code == 403:
        prefix = "Tokenlane refused the image request. Check key permissions and account access."
    elif status_code == 429:
        prefix = "Tokenlane image generation is rate limited. Wait a moment and retry."
    elif status_code == 503:
        prefix = "Tokenlane image generation is temporarily unavailable. Retry later or check Tokenlane image service status."
    else:
        prefix = f"Tokenlane Images API returned HTTP {status_code}."
    return f"{prefix} Detail: {detail}" if detail else prefix


def image_request_body(prompt: str, model: str, size: str) -> bytes:
    return json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "size": size,
        },
        ensure_ascii=False,
    ).encode("utf-8")


def parse_api_response(raw: bytes) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise TokenlaneImageError("Tokenlane Images API returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise TokenlaneImageError("Tokenlane Images API returned an unexpected JSON shape.")
    return payload


def curl_config_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def request_image_with_curl(api_key: str, body: bytes, timeout: int) -> dict:
    curl = shutil.which("curl")
    if not curl:
        raise FileNotFoundError("curl not found")

    marker = "\n__TOKENLANE_HTTP_STATUS__:"
    body_path = ""
    config_path = ""
    try:
        with tempfile.NamedTemporaryFile("wb", prefix="image2-body-", delete=False) as body_file:
            body_file.write(body)
            body_path = body_file.name
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="image2-curl-", delete=False) as config_file:
            config_file.write(f'header = "Authorization: Bearer {curl_config_quote(api_key)}"\n')
            config_file.write('header = "Content-Type: application/json"\n')
            config_file.write('header = "Accept: application/json"\n')
            config_file.write(f'data-binary = "@{curl_config_quote(body_path)}"\n')
            config_path = config_file.name

        command = [
            curl,
            "-sS",
            "--max-time",
            str(timeout),
            "-X",
            "POST",
            TOKENLANE_ENDPOINT,
            "--config",
            config_path,
            "-w",
            marker + "%{http_code}",
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        for path in (body_path, config_path):
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    stdout = completed.stdout.decode("utf-8", errors="replace")
    if marker not in stdout:
        stderr = redact_sensitive(completed.stderr.decode("utf-8", errors="replace").strip())
        raise TokenlaneImageError(f"Tokenlane Images API request failed: {stderr or 'curl failed'}")

    response_text, status_text = stdout.rsplit(marker, 1)
    try:
        status_code = int(status_text.strip())
    except ValueError:
        status_code = 0

    response_bytes = response_text.encode("utf-8")
    if status_code < 200 or status_code >= 300:
        raise TokenlaneImageError(friendly_http_error(status_code, parse_error_body(response_bytes)))

    return parse_api_response(response_bytes)


def request_image_with_urllib(api_key: str, body: bytes, timeout: int) -> dict:
    request = urllib.request.Request(
        TOKENLANE_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_api_response(response.read())
    except urllib.error.HTTPError as exc:
        raise TokenlaneImageError(friendly_http_error(exc.code, parse_error_body(exc.read()))) from exc
    except urllib.error.URLError as exc:
        raise TokenlaneImageError(f"Tokenlane Images API request failed: {exc.reason}") from exc


def request_image(api_key: str, prompt: str, model: str, size: str, timeout: int) -> dict:
    body = image_request_body(prompt, model, size)
    try:
        return request_image_with_curl(api_key, body, timeout)
    except FileNotFoundError:
        return request_image_with_urllib(api_key, body, timeout)


def save_images(payload: dict, output_dir: Path, prefix: str) -> list[Path]:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise TokenlaneImageError("Tokenlane Images API response did not contain data[].b64_json.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise TokenlaneImageError(f"Tokenlane Images API response data[{index - 1}] is invalid.")

        b64_json = item.get("b64_json")
        if not isinstance(b64_json, str) or not b64_json.strip():
            raise TokenlaneImageError(f"Tokenlane Images API response data[{index - 1}] did not contain b64_json.")

        image_bytes = decode_b64_image(b64_json)
        filename = f"{prefix}-{time.time_ns()}-{secrets.token_hex(3)}-{index}{image_extension(image_bytes)}"
        output_path = output_dir / filename
        output_path.write_bytes(image_bytes)
        output_paths.append(output_path)
    return output_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate images through Tokenlane Images API.")
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Accepted for compatibility; the API call always uses gpt-image-2")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Image size or alias: square, landscape, portrait, auto")
    parser.add_argument("--count", type=int, default=1, help=f"Number of images to generate, 1-{MAX_COUNT}")
    parser.add_argument("--output-dir", default="/tmp/Image2", help="Directory for generated images")
    parser.add_argument("--timeout", type=int, default=180, help="Request timeout in seconds")
    args = parser.parse_args()

    try:
        prompt = validate_prompt(args.prompt)
        count = validate_count(args.count)
        timeout = validate_timeout(args.timeout)
        size = normalize_size(args.size)
        model, note = normalize_model(args.model)
    except TokenlaneImageError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    api_key = resolve_api_key()
    if not api_key:
        print(
            "No Tokenlane API key found. Set TOKENLANE_API_KEY, IMAGE2_API_KEY, or create ~/.codex/Image2/api_key. "
            "macOS Codex Desktop may not inherit variables exported in a separate terminal.",
            file=sys.stderr,
        )
        return 2

    output_paths: list[Path] = []
    try:
        for _ in range(count):
            payload = request_image(api_key, prompt, model, size, timeout)
            output_paths.extend(save_images(payload, Path(args.output_dir), "Image2"))
    except TokenlaneImageError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    resolved_paths = [str(path.resolve()) for path in output_paths]
    result = {
        "output_path": resolved_paths[0] if resolved_paths else "",
        "output_paths": resolved_paths,
        "model": model,
        "size": size,
        "count": count,
    }
    if note:
        result["note"] = note
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
