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
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_ROUTES = {"codex_builtin_imagegen", "tokenlane_image2"}
DEFAULT_IMAGE2_SCRIPT = "/Users/fly/.codex/skills/Image2/scripts/generate_image.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or run Image2 generation for an image deck.")
    parser.add_argument("--workspace", required=True, help="Deck workspace root.")
    parser.add_argument("--route", required=True, choices=sorted(ALLOWED_ROUTES), help="Image2 route to use.")
    parser.add_argument(
        "--mode",
        default="plan",
        choices=["plan", "generate-tokenlane", "record"],
        help="plan writes a resumable queue; generate-tokenlane calls Tokenlane; record copies one built-in image_gen output.",
    )
    parser.add_argument("--page-prompts", help="Defaults to <workspace>/authoring/page_prompts.json.")
    parser.add_argument("--images-dir", help="Defaults to <workspace>/images.")
    parser.add_argument("--manifest", help="Defaults to <workspace>/authoring/image_manifest.json.")
    parser.add_argument("--queue", help="Defaults to <workspace>/authoring/image_generation_queue.json.")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of missing slides to include in plan output.")
    parser.add_argument("--size", default="1536x864", help="Image2 size for Tokenlane generation.")
    parser.add_argument("--quality", default="high", help="Image2 quality for Tokenlane generation.")
    parser.add_argument("--preset", default="ppt-diagram", help="Image2 preset for Tokenlane generation.")
    parser.add_argument("--timeout", type=int, default=300, help="Tokenlane request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Tokenlane retries per slide.")
    parser.add_argument("--image2-script", default=DEFAULT_IMAGE2_SCRIPT, help="Tokenlane Image2 script path.")
    parser.add_argument("--python", default=sys.executable, help="Python executable for Tokenlane script.")
    parser.add_argument("--slide-number", type=int, help="Slide number for --mode record.")
    parser.add_argument("--source-image", help="Generated image path to record for --mode record.")
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
) -> Path:
    if not source_image.exists():
        raise SystemExit(f"source image not found: {source_image}")
    images_dir.mkdir(parents=True, exist_ok=True)
    target = images_dir / f"slide-{slide_no:02d}{source_image.suffix.lower() or '.png'}"
    if source_image.resolve() != target.resolve():
        shutil.copy2(source_image, target)
    manifest["image_route"] = route
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    upsert_manifest_record(
        manifest,
        {
            "slide_number": slide_no,
            "image_route": route,
            "image": str(target),
            "prompt_ref": prompt_ref,
            "source_generated_path": str(source_image),
            "provider_output_id": provider_output_id,
            "generation_status": "completed",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    write_json(manifest_path, manifest)
    return target


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
    timeout: int,
) -> dict[str, Any]:
    cmd = [
        python,
        str(image2_script),
        "--prompt",
        prompt,
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
                    timeout=args.timeout,
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
    workspace = Path(args.workspace).expanduser().resolve()
    authoring = workspace / "authoring"
    page_prompts = Path(args.page_prompts).expanduser().resolve() if args.page_prompts else authoring / "page_prompts.json"
    images_dir = Path(args.images_dir).expanduser().resolve() if args.images_dir else workspace / "images"
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else authoring / "image_manifest.json"
    queue_path = Path(args.queue).expanduser().resolve() if args.queue else authoring / "image_generation_queue.json"

    records = records_from_json(page_prompts)
    manifest = load_manifest(manifest_path, args.route)
    queued = queue_records(records, manifest, images_dir)
    queue_payload = write_queue(queue_path, args.route, queued, args.batch_size)

    result: dict[str, Any] = {
        "workspace": str(workspace),
        "route": args.route,
        "mode": args.mode,
        "page_prompts": str(page_prompts),
        "images_dir": str(images_dir),
        "manifest": str(manifest_path),
        "queue": str(queue_path),
        "pending_count": len(queued),
        "next_batch_count": len(queue_payload["next_batch"]),
    }

    if args.mode == "record":
        if args.route != "codex_builtin_imagegen":
            raise SystemExit("--mode record is for built-in membership image_gen outputs")
        if not args.slide_number or not args.source_image:
            raise SystemExit("--mode record requires --slide-number and --source-image")
        target = record_image(
            manifest_path=manifest_path,
            manifest=manifest,
            route=args.route,
            images_dir=images_dir,
            slide_no=args.slide_number,
            source_image=Path(args.source_image).expanduser().resolve(),
            prompt_ref=f"slide-{args.slide_number:02d}",
            provider_output_id=args.provider_output_id,
        )
        result["recorded_image"] = str(target)
    elif args.mode == "generate-tokenlane":
        if args.route != "tokenlane_image2":
            raise SystemExit("--mode generate-tokenlane requires --route tokenlane_image2")
        result["generated"] = generate_tokenlane(args, queued, manifest, manifest_path, images_dir)
    elif args.mode == "plan":
        pass

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
