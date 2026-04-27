#!/usr/bin/env python3
"""Prepare, generate, or record Image2 slide images for slide-maker decks.

This utility keeps long image decks resumable:
- reads authoring/page_prompts.json records;
- writes a generation queue for membership image_gen batches;
- calls Tokenlane Image2 for API-login mode with retries and long timeout;
- records completed images into authoring/image_manifest.json.

It does not create slide content. It only operationalizes already-authored
page_prompts records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from detect_image_route import detect_image_route

ALLOWED_ROUTES = {"codex_builtin_imagegen", "tokenlane_image2"}
ROUTE_CHOICES = sorted(ALLOWED_ROUTES | {"auto"})
REQUIRED_IMAGE2_MODEL = "gpt-image-2"
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}
DEFAULT_IMAGE2_SCRIPT = "/Users/fly/.codex/skills/Image2/scripts/generate_image.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or run Image2 generation for an image deck.")
    parser.add_argument("--workspace", required=True, help="Deck workspace root.")
    parser.add_argument("--route", required=True, choices=ROUTE_CHOICES, help="Image2 route to use.")
    parser.add_argument(
        "--mode",
        default="plan",
        choices=["plan", "status", "builtin-start", "builtin-capture", "generate-tokenlane", "record"],
        help=(
            "plan writes a resumable queue; builtin-start snapshots generated_images before membership "
            "image_gen; builtin-capture copies the new built-in image_gen output; generate-tokenlane "
            "calls Tokenlane; record copies one explicit image path."
        ),
    )
    parser.add_argument("--page-prompts", help="Defaults to <workspace>/authoring/page_prompts.json.")
    parser.add_argument("--images-dir", help="Defaults to <workspace>/images.")
    parser.add_argument("--manifest", help="Defaults to <workspace>/authoring/image_manifest.json.")
    parser.add_argument("--queue", help="Defaults to <workspace>/authoring/image_generation_queue.json.")
    parser.add_argument("--capture", help="Defaults to <workspace>/authoring/builtin_imagegen_capture.json.")
    parser.add_argument(
        "--generated-root",
        help="Built-in image_gen output root. Defaults to ${CODEX_HOME:-~/.codex}/generated_images.",
    )
    parser.add_argument("--batch-size", type=int, default=3, help="Number of missing slides to include in plan output.")
    parser.add_argument("--size", default="1536x864", help="Image2 size for Tokenlane generation.")
    parser.add_argument("--quality", default="high", help="Image2 quality for Tokenlane generation.")
    parser.add_argument("--preset", default="ppt-diagram", help="Image2 preset for Tokenlane generation.")
    parser.add_argument(
        "--model",
        default=REQUIRED_IMAGE2_MODEL,
        help="Locked Image2 model for Tokenlane/API mode. Must be gpt-image-2.",
    )
    parser.add_argument("--timeout", type=int, default=300, help="Tokenlane request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Tokenlane retries per slide.")
    parser.add_argument("--image2-script", default=DEFAULT_IMAGE2_SCRIPT, help="Tokenlane Image2 script path.")
    parser.add_argument("--python", default=sys.executable, help="Python executable for Tokenlane script.")
    parser.add_argument("--slide-number", type=int, help="Slide number for --mode record.")
    parser.add_argument("--source-image", help="Generated image path to record for --mode record.")
    parser.add_argument(
        "--candidate-index",
        type=int,
        help="1-based candidate index for --mode builtin-capture when multiple new generated images exist.",
    )
    parser.add_argument(
        "--auto-select-newest",
        action="store_true",
        help="Allow builtin-capture to select newest image when multiple candidates exist.",
    )
    parser.add_argument("--provider-output-id", default="", help="Optional provider output id for --mode record.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without generating or copying.")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"required file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_generated_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return base / "generated_images"


def generated_file_records(root: Path, *, include_sha256: bool = False) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        record = {
            "path": str(path.resolve()),
            "name": path.name,
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }
        if include_sha256:
            try:
                record["sha256"] = sha256_file(path)
            except OSError:
                continue
        records.append(record)
    records.sort(key=lambda item: (int(item["mtime_ns"]), str(item["path"])), reverse=True)
    return records


def records_from_json(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("slides"), list):
        records = data["slides"]
    elif isinstance(data, list):
        records = data
    else:
        raise SystemExit("page_prompts must be a list or an object with slides[]")
    clean: list[dict[str, Any]] = []
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise SystemExit(f"page_prompts record {idx} must be an object")
        clean.append(record)
    return clean


def prompt_for(record: dict[str, Any]) -> str:
    prompt = str(record.get("image_prompt") or "").strip()
    if prompt:
        return prompt
    visible_items = record.get("visible_items")
    labels = ""
    if isinstance(visible_items, list) and visible_items:
        labels = "Use these exact Simplified Chinese labels only: " + "；".join(str(x) for x in visible_items if str(x).strip())
    return "\n".join(
        part
        for part in [
            "16:9 full-slide academic infographic.",
            f"Page type: {record.get('page_type', '')}.",
            f"Visualization type: {record.get('visualization_type', '')}.",
            f"Visible title: {record.get('page_text') or record.get('visible_text') or ''}.",
            labels,
            f"Design: {record.get('visual_brief', '')}",
            "Rules: large crisp Simplified Chinese text, all horizontal, generous margins, no English filler, no extra labels, no logos, no watermark, no fake charts.",
        ]
        if str(part).strip()
    )


def slide_number(record: dict[str, Any], fallback: int) -> int:
    value = record.get("slide_number", fallback)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise SystemExit(f"invalid slide_number: {value!r}") from None


def load_manifest(path: Path, route: str) -> dict[str, Any]:
    if path.exists():
        data = read_json(path)
        if not isinstance(data, dict):
            raise SystemExit("image_manifest must be a JSON object")
        existing_route = str(data.get("image_route") or data.get("route") or "").strip()
        if existing_route and existing_route != route:
            raise SystemExit(
                f"image_manifest route {existing_route} does not match requested route {route}; "
                "do not mix membership and API routes in one default run"
            )
        data.setdefault("image_route", route)
        data.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("slides", [])
        if not isinstance(data["slides"], list):
            raise SystemExit("image_manifest slides must be a list")
        return data
    return {
        "image_route": route,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "slides": [],
    }


def upsert_manifest_record(manifest: dict[str, Any], record: dict[str, Any]) -> None:
    slide_no = record["slide_number"]
    slides = manifest.setdefault("slides", [])
    for idx, existing in enumerate(slides):
        if isinstance(existing, dict) and existing.get("slide_number") == slide_no:
            slides[idx] = record
            return
    slides.append(record)
    slides.sort(key=lambda item: int(item.get("slide_number", 0)) if isinstance(item, dict) else 0)


def completed_slide_numbers(manifest: dict[str, Any], images_dir: Path) -> set[int]:
    done: set[int] = set()
    for record in manifest.get("slides", []):
        if not isinstance(record, dict):
            continue
        try:
            slide_no = int(record.get("slide_number"))
        except (TypeError, ValueError):
            continue
        image_value = record.get("image") or record.get("image_path") or record.get("workspace_image")
        if image_value and (images_dir / Path(str(image_value)).name).exists():
            done.add(slide_no)
    return done


def manifest_slide_numbers(manifest: dict[str, Any]) -> set[int]:
    numbers: set[int] = set()
    for record in manifest.get("slides", []):
        if not isinstance(record, dict):
            continue
        try:
            numbers.add(int(record.get("slide_number")))
        except (TypeError, ValueError):
            continue
    return numbers


def queue_records(page_records: list[dict[str, Any]], manifest: dict[str, Any], images_dir: Path) -> list[dict[str, Any]]:
    done = completed_slide_numbers(manifest, images_dir)
    queued: list[dict[str, Any]] = []
    for idx, record in enumerate(page_records, start=1):
        slide_no = slide_number(record, idx)
        target = images_dir / f"slide-{slide_no:02d}.png"
        if slide_no in done and target.exists():
            continue
        queued.append(
            {
                "slide_number": slide_no,
                "target_image": str(target),
                "prompt_ref": f"slide-{slide_no:02d}",
                "prompt": prompt_for(record),
                "content_density": record.get("content_density", ""),
                "visualization_type": record.get("visualization_type", ""),
                "visible_items": record.get("visible_items", []),
                "text_risk_level": record.get("text_risk_level", ""),
            }
        )
    return queued


def queued_item_for_slide(queued: list[dict[str, Any]], slide_no: int) -> dict[str, Any] | None:
    for item in queued:
        if int(item["slide_number"]) == slide_no:
            return item
    return None


def choose_slide_number(args: argparse.Namespace, queued: list[dict[str, Any]], page_records: list[dict[str, Any]]) -> int:
    if args.slide_number:
        return args.slide_number
    if queued:
        return int(queued[0]["slide_number"])
    if page_records:
        return slide_number(page_records[0], 1)
    raise SystemExit("no slide records available")


def write_queue(path: Path, route: str, queued: list[dict[str, Any]], batch_size: int) -> dict[str, Any]:
    payload = {
        "route": route,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "batch_size": batch_size,
        "pending_count": len(queued),
        "next_batch": queued[: max(1, batch_size)],
        "pending": queued,
    }
    write_json(path, payload)
    return payload


def build_status(
    *,
    route: str,
    route_detection: dict[str, Any],
    workspace: Path,
    page_prompts: Path,
    images_dir: Path,
    manifest_path: Path,
    queue_path: Path,
    capture_path: Path,
    generated_root: Path,
    queued: list[dict[str, Any]],
    queue_payload: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    next_slide = queued[0] if queued else None
    manifest_done = manifest_slide_numbers(manifest)
    missing_manifest_records = [
        int(item["slide_number"])
        for item in queued
        if int(item["slide_number"]) not in manifest_done
    ]
    if not queued:
        next_action = "all_slide_images_recorded"
    elif route == "codex_builtin_imagegen":
        next_action = "run builtin-start, call image_gen with next_prompt, then run builtin-capture"
    elif route == "tokenlane_image2":
        next_action = "run generate-tokenlane"
    else:
        next_action = "resolve route"
    return {
        "workspace": str(workspace),
        "route": route,
        "route_detection": route_detection,
        "page_prompts": str(page_prompts),
        "images_dir": str(images_dir),
        "manifest": str(manifest_path),
        "queue": str(queue_path),
        "capture": str(capture_path),
        "generated_root": str(generated_root),
        "pending_count": len(queued),
        "next_action": next_action,
        "next_slide_number": next_slide.get("slide_number") if next_slide else None,
        "next_prompt": next_slide.get("prompt") if next_slide else "",
        "missing_manifest_records": missing_manifest_records,
        "next_batch": queue_payload.get("next_batch", []),
    }


def record_image(
    *,
    manifest_path: Path,
    manifest: dict[str, Any],
    route: str,
    images_dir: Path,
    slide_no: int,
    source_image: Path,
    prompt_ref: str,
    provider_output_id: str = "",
    image_model: str = REQUIRED_IMAGE2_MODEL,
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    if not source_image.exists():
        raise SystemExit(f"source image not found: {source_image}")
    images_dir.mkdir(parents=True, exist_ok=True)
    target = images_dir / f"slide-{slide_no:02d}{source_image.suffix.lower() or '.png'}"
    if source_image.resolve() != target.resolve():
        shutil.copy2(source_image, target)
    manifest["image_route"] = route
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_record = {
        "slide_number": slide_no,
        "image_route": route,
        "image": str(target),
        "prompt_ref": prompt_ref,
        "source_generated_path": str(source_image),
        "provider_output_id": provider_output_id,
        "image_model": image_model,
        "model": image_model,
        "generation_status": "completed",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_fields:
        manifest_record.update(extra_fields)
    upsert_manifest_record(manifest, manifest_record)
    write_json(manifest_path, manifest)
    return target


def builtin_start(
    *,
    args: argparse.Namespace,
    route: str,
    workspace: Path,
    capture_path: Path,
    generated_root: Path,
    queued: list[dict[str, Any]],
    page_records: list[dict[str, Any]],
) -> dict[str, Any]:
    if route != "codex_builtin_imagegen":
        raise SystemExit("--mode builtin-start requires --route codex_builtin_imagegen")
    slide_no = choose_slide_number(args, queued, page_records)
    queued_item = queued_item_for_slide(queued, slide_no) or {
        "slide_number": slide_no,
        "prompt_ref": f"slide-{slide_no:02d}",
    }
    files = generated_file_records(generated_root)
    payload = {
        "route": route,
        "capture_method": "generated_images_delta",
        "workspace": str(workspace),
        "generated_root": str(generated_root),
        "slide_number": slide_no,
        "prompt_ref": queued_item.get("prompt_ref") or f"slide-{slide_no:02d}",
        "target_image": queued_item.get("target_image", ""),
        "prompt": queued_item.get("prompt", ""),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "baseline_count": len(files),
        "baseline": files,
    }
    write_json(capture_path, payload)
    return payload


def candidate_delta(capture: dict[str, Any], generated_root: Path) -> list[dict[str, Any]]:
    current = generated_file_records(generated_root, include_sha256=True)
    baseline = capture.get("baseline")
    if not isinstance(baseline, list):
        raise SystemExit("capture file missing baseline[]; run builtin-start first")
    baseline_by_path = {
        str(item.get("path")): item
        for item in baseline
        if isinstance(item, dict) and item.get("path")
    }
    candidates: list[dict[str, Any]] = []
    for item in current:
        old = baseline_by_path.get(str(item["path"]))
        if old is None:
            candidate = dict(item)
            candidate["delta_reason"] = "new_path"
            candidates.append(candidate)
            continue
        if old.get("size") != item.get("size") or old.get("mtime_ns") != item.get("mtime_ns"):
            candidate = dict(item)
            candidate["delta_reason"] = "changed_file"
            candidates.append(candidate)
    candidates.sort(key=lambda item: (int(item["mtime_ns"]), str(item["path"])), reverse=True)
    return candidates


def builtin_capture(
    *,
    args: argparse.Namespace,
    manifest_path: Path,
    manifest: dict[str, Any],
    images_dir: Path,
    capture_path: Path,
    generated_root: Path,
) -> dict[str, Any]:
    if args.route != "codex_builtin_imagegen":
        raise SystemExit("--mode builtin-capture requires --route codex_builtin_imagegen")
    capture = read_json(capture_path)
    if not isinstance(capture, dict):
        raise SystemExit("builtin imagegen capture file must be a JSON object")

    slide_no = args.slide_number or int(capture.get("slide_number") or 0)
    if not slide_no:
        raise SystemExit("--mode builtin-capture requires --slide-number or a capture slide_number")
    prompt_ref = str(capture.get("prompt_ref") or f"slide-{slide_no:02d}")

    source_image: Path
    candidates: list[dict[str, Any]]
    selected_index = 1
    selection_reason = "single_candidate"
    if args.source_image:
        source_image = Path(args.source_image).expanduser().resolve()
        if not source_image.exists():
            raise SystemExit(f"source image not found: {source_image}")
        stat = source_image.stat()
        candidates = [
            {
                "path": str(source_image),
                "name": source_image.name,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "sha256": sha256_file(source_image),
                "delta_reason": "manual_source_image",
            }
        ]
        selection_reason = "manual_source_image"
    else:
        candidates = candidate_delta(capture, generated_root)
        capture["captured_candidates"] = candidates
        capture["captured_candidate_count"] = len(candidates)
        capture["captured_at"] = datetime.now(timezone.utc).isoformat()
        write_json(capture_path, capture)
        if not candidates:
            raise SystemExit(
                "no new built-in image_gen output found under generated_images; "
                "rerun image_gen after builtin-start or pass --source-image"
            )
        if len(candidates) > 1 and not args.candidate_index and not args.auto_select_newest:
            raise SystemExit(
                "multiple new built-in image_gen outputs found; rerun with --candidate-index, "
                f"--source-image, or --auto-select-newest. Candidates were written to {capture_path}"
            )
        if args.candidate_index and (args.candidate_index < 1 or args.candidate_index > len(candidates)):
            raise SystemExit(
                f"--candidate-index must be between 1 and {len(candidates)}; "
                f"candidates were written to {capture_path}"
            )
        selected_index = args.candidate_index or 1
        selection_reason = "candidate_index" if args.candidate_index else (
            "auto_select_newest" if len(candidates) > 1 else "single_candidate"
        )
        source_image = Path(str(candidates[selected_index - 1]["path"])).expanduser().resolve()

    source_sha256 = sha256_file(source_image)
    capture_method = "manual_source_image" if args.source_image else "generated_images_delta"
    target = record_image(
        manifest_path=manifest_path,
        manifest=manifest,
        route="codex_builtin_imagegen",
        images_dir=images_dir,
        slide_no=slide_no,
        source_image=source_image,
        prompt_ref=prompt_ref,
        provider_output_id=args.provider_output_id,
        extra_fields={
            "capture_method": capture_method,
            "capture_root": str(generated_root),
            "source_sha256": source_sha256,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "selection_reason": selection_reason,
            "capture_candidate_count": len(candidates),
        },
    )
    result = {
        "slide_number": slide_no,
        "captured_image": str(target),
        "source_generated_path": str(source_image),
        "source_sha256": source_sha256,
        "candidate_count": len(candidates),
        "candidate_index": selected_index,
        "selection_reason": selection_reason,
        "capture": str(capture_path),
    }
    if len(candidates) > 1:
        result["warning"] = (
            "multiple new generated images found; selected candidate by explicit index or --auto-select-newest"
        )
    return result


def run_tokenlane(
    *,
    python: str,
    image2_script: Path,
    prompt: str,
    output_dir: Path,
    filename_prefix: str,
    size: str,
    quality: str,
    preset: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    if model != REQUIRED_IMAGE2_MODEL:
        raise RuntimeError(f"slide-maker API route is locked to {REQUIRED_IMAGE2_MODEL}; got {model}")
    cmd = [
        python,
        str(image2_script),
        "--prompt",
        prompt,
        "--model",
        REQUIRED_IMAGE2_MODEL,
        "--size",
        size,
        "--quality",
        quality,
        "--preset",
        preset,
        "--count",
        "1",
        "--timeout",
        str(timeout),
        "--filename-prefix",
        filename_prefix,
        "--output-dir",
        str(output_dir),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"Tokenlane exited {proc.returncode}").strip())
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not parse Tokenlane output: {proc.stdout[:500]}") from exc


def generate_tokenlane(args: argparse.Namespace, queued: list[dict[str, Any]], manifest: dict[str, Any], manifest_path: Path, images_dir: Path) -> list[dict[str, Any]]:
    if args.model != REQUIRED_IMAGE2_MODEL:
        raise SystemExit(f"slide-maker API route is locked to {REQUIRED_IMAGE2_MODEL}; got {args.model}")
    image2_script = Path(args.image2_script).expanduser().resolve()
    if not image2_script.exists():
        raise SystemExit(f"Image2 script not found: {image2_script}")
    generated: list[dict[str, Any]] = []
    temp_dir = images_dir / "_tokenlane_raw"
    temp_dir.mkdir(parents=True, exist_ok=True)
    for item in queued:
        slide_no = int(item["slide_number"])
        target = images_dir / f"slide-{slide_no:02d}.png"
        if target.exists():
            continue
        last_error = ""
        for attempt in range(1, max(1, args.retries) + 1):
            if args.dry_run:
                generated.append({"slide_number": slide_no, "dry_run": True, "attempt": attempt})
                break
            try:
                result = run_tokenlane(
                    python=args.python,
                    image2_script=image2_script,
                    prompt=item["prompt"],
                    output_dir=temp_dir,
                    filename_prefix=f"slide-{slide_no:02d}",
                    size=args.size,
                    quality=args.quality,
                    preset=args.preset,
                    model=args.model,
                    timeout=args.timeout,
                )
                result_model = str(result.get("model") or "").strip()
                if result_model != REQUIRED_IMAGE2_MODEL:
                    raise RuntimeError(
                        f"Tokenlane Image2 returned model {result_model or '<empty>'}; "
                        f"expected {REQUIRED_IMAGE2_MODEL}"
                    )
                output_path = Path(result.get("output_path") or (result.get("output_paths") or [""])[0])
                if not output_path.exists():
                    raise RuntimeError(f"Tokenlane output image not found: {output_path}")
                copied = record_image(
                    manifest_path=manifest_path,
                    manifest=manifest,
                    route="tokenlane_image2",
                    images_dir=images_dir,
                    slide_no=slide_no,
                    source_image=output_path,
                    prompt_ref=item["prompt_ref"],
                    provider_output_id=str(result.get("response_id") or ""),
                    image_model=REQUIRED_IMAGE2_MODEL,
                    extra_fields={
                        "api": str(result.get("api") or "images"),
                        "request_kind": "tokenlane_image2_generation",
                        "model_lock": REQUIRED_IMAGE2_MODEL,
                    },
                )
                generated.append({"slide_number": slide_no, "image": str(copied), "attempt": attempt})
                break
            except RuntimeError as exc:
                last_error = str(exc)
                if attempt >= args.retries:
                    generated.append({"slide_number": slide_no, "error": last_error, "attempts": attempt})
        if generated and generated[-1].get("error"):
            break
    return generated


def main() -> int:
    args = parse_args()
    route_detection = detect_image_route(args.route)
    resolved_route = str(route_detection["image_route"])
    args.route = resolved_route
    workspace = Path(args.workspace).expanduser().resolve()
    authoring = workspace / "authoring"
    page_prompts = Path(args.page_prompts).expanduser().resolve() if args.page_prompts else authoring / "page_prompts.json"
    images_dir = Path(args.images_dir).expanduser().resolve() if args.images_dir else workspace / "images"
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else authoring / "image_manifest.json"
    queue_path = Path(args.queue).expanduser().resolve() if args.queue else authoring / "image_generation_queue.json"
    capture_path = Path(args.capture).expanduser().resolve() if args.capture else authoring / "builtin_imagegen_capture.json"
    generated_root = Path(args.generated_root).expanduser().resolve() if args.generated_root else default_generated_root()

    records = records_from_json(page_prompts)
    manifest = load_manifest(manifest_path, resolved_route)
    queued = queue_records(records, manifest, images_dir)
    queue_payload = write_queue(queue_path, resolved_route, queued, args.batch_size)

    result: dict[str, Any] = {
        "workspace": str(workspace),
        "route": resolved_route,
        "route_detection": route_detection,
        "mode": args.mode,
        "page_prompts": str(page_prompts),
        "images_dir": str(images_dir),
        "manifest": str(manifest_path),
        "queue": str(queue_path),
        "capture": str(capture_path),
        "generated_root": str(generated_root),
        "pending_count": len(queued),
        "next_batch_count": len(queue_payload["next_batch"]),
    }

    if args.mode == "status":
        result["status"] = build_status(
            route=resolved_route,
            route_detection=route_detection,
            workspace=workspace,
            page_prompts=page_prompts,
            images_dir=images_dir,
            manifest_path=manifest_path,
            queue_path=queue_path,
            capture_path=capture_path,
            generated_root=generated_root,
            queued=queued,
            queue_payload=queue_payload,
            manifest=manifest,
        )
    elif args.mode == "builtin-start":
        result["builtin_start"] = builtin_start(
            args=args,
            route=resolved_route,
            workspace=workspace,
            capture_path=capture_path,
            generated_root=generated_root,
            queued=queued,
            page_records=records,
        )
    elif args.mode == "builtin-capture":
        result["builtin_capture"] = builtin_capture(
            args=args,
            manifest_path=manifest_path,
            manifest=manifest,
            images_dir=images_dir,
            capture_path=capture_path,
            generated_root=generated_root,
        )
    elif args.mode == "record":
        if resolved_route != "codex_builtin_imagegen":
            raise SystemExit("--mode record is for built-in membership image_gen outputs")
        if not args.slide_number or not args.source_image:
            raise SystemExit("--mode record requires --slide-number and --source-image")
        target = record_image(
            manifest_path=manifest_path,
            manifest=manifest,
            route=resolved_route,
            images_dir=images_dir,
            slide_no=args.slide_number,
            source_image=Path(args.source_image).expanduser().resolve(),
            prompt_ref=f"slide-{args.slide_number:02d}",
            provider_output_id=args.provider_output_id,
            extra_fields={
                "capture_method": "manual_source_image",
                "capture_root": str(generated_root),
                "source_sha256": sha256_file(Path(args.source_image).expanduser().resolve()),
                "captured_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        result["recorded_image"] = str(target)
    elif args.mode == "generate-tokenlane":
        if resolved_route != "tokenlane_image2":
            raise SystemExit("--mode generate-tokenlane requires --route tokenlane_image2")
        result["generated"] = generate_tokenlane(args, queued, manifest, manifest_path, images_dir)
    elif args.mode == "plan":
        pass

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
