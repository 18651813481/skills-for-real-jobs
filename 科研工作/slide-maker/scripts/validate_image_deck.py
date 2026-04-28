#!/usr/bin/env python3
"""Validate that a slide-maker image deck really used an Image2 route."""

from __future__ import annotations

import argparse
import json
import re
import struct
import zipfile
from pathlib import Path
from typing import Any

from detect_image_route import detect_image_route

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg"}
ALLOWED_ROUTES = {"codex_builtin_imagegen", "tokenlane_image2"}
ROUTE_CHOICES = sorted(ALLOWED_ROUTES | {"auto"})
REQUIRED_IMAGE2_MODEL = "gpt-image-2"
GOOD_STATUSES = {"completed", "succeeded", "success", "ok"}
SUSPICIOUS_SCRIPT_PATTERNS = [
    "from PIL import",
    "import PIL",
    "ImageDraw",
    "matplotlib",
    "cairosvg",
    "playwright",
    "selenium",
    "html2canvas",
    "screenshot",
    "local deterministic",
]
GENERIC_VISUAL_PHRASES = [
    "background",
    "背景",
    "科技背景",
    "abstract background",
    "generic",
    "简单背景",
    "纯背景",
]
DENSE_DENSITY_VALUES = {"dense", "table_heavy", "high_infographic"}
ALLOWED_DENSITY_VALUES = {"sparse", "normal", "dense", "table_heavy", "high_infographic"}
ALLOWED_TEXT_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_VISUALIZATION_TYPES = {
    "infographic",
    "concept_map",
    "workflow",
    "comparison",
    "comparison_matrix",
    "timeline",
    "roadmap",
    "metrics",
    "metrics_card",
    "table_visualization",
    "scorecard",
    "risk_map",
    "decision_tree",
    "source_quote",
    "closing",
    "scene_explainer",
}
DENSE_VISUALIZATION_TYPES = {
    "infographic",
    "concept_map",
    "workflow",
    "comparison",
    "comparison_matrix",
    "timeline",
    "roadmap",
    "metrics",
    "metrics_card",
    "table_visualization",
    "scorecard",
    "risk_map",
    "decision_tree",
}


def validate_deck_contract(deck_root: Path, errors: list[str]) -> dict[str, Any]:
    path = deck_root / "authoring" / "deck_contract.json"
    summary = {
        "path": str(path),
        "deck_format": None,
        "image_required": None,
        "native_editable_requested": None,
        "pptx_backend_role": None,
        "deck_format_ok": False,
    }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"deck_contract.json not found: {path}")
        return summary
    except json.JSONDecodeError as exc:
        errors.append(f"deck_contract.json invalid JSON: {exc}")
        return summary
    if not isinstance(data, dict):
        errors.append("deck_contract.json must be an object")
        return summary
    summary.update(
        {
            "deck_format": data.get("deck_format"),
            "image_required": data.get("image_required"),
            "native_editable_requested": data.get("native_editable_requested"),
            "pptx_backend_role": data.get("pptx_backend_role"),
        }
    )
    contract_errors: list[str] = []
    if data.get("deck_format") != "image_deck":
        contract_errors.append("deck_contract.json deck_format must be image_deck for image deck validation")
    if data.get("image_required") is not True:
        contract_errors.append("deck_contract.json image_required must be true")
    if data.get("native_editable_requested") is not False:
        contract_errors.append("deck_contract.json native_editable_requested must be false")
    if data.get("pptx_backend_role") != "image_container_only":
        contract_errors.append("deck_contract.json pptx_backend_role must be image_container_only")
    errors.extend(contract_errors)
    summary["deck_format_ok"] = not contract_errors
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a slide-maker Image2 image deck before delivery."
    )
    parser.add_argument("--pptx", required=True, help="PPTX image deck path.")
    parser.add_argument("--images-dir", required=True, help="Directory with slide images.")
    parser.add_argument("--page-prompts", required=True, help="authoring/page_prompts.json path.")
    parser.add_argument("--source-map", required=True, help="authoring/source_map.json path.")
    parser.add_argument("--image-manifest", required=True, help="authoring/image_manifest.json path.")
    parser.add_argument(
        "--expected-route",
        choices=ROUTE_CHOICES,
        help="Optional expected route from login mode; fails if manifest route differs.",
    )
    parser.add_argument("--qa-report", help="Optional validation report JSON path.")
    parser.add_argument("--deck-root", help="Deck workspace root. Defaults to PPTX parent.")
    parser.add_argument(
        "--allow-non-image2",
        action="store_true",
        help="Allow a non-Image2 fallback only with --non-image2-approval.",
    )
    parser.add_argument(
        "--non-image2-approval",
        help='JSON file containing {"approved": true} for an explicit fallback.',
    )
    parser.add_argument(
        "--allow-non-16x9",
        action="store_true",
        help="Warn instead of failing for non-16:9 images.",
    )
    return parser.parse_args()


def natural_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"required file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        header = fh.read(24)
    if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", header[16:24])
    return None


def jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as fh:
        data = fh.read()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data):
        while i < len(data) and data[i] == 0xFF:
            i += 1
        if i >= len(data):
            break
        marker = data[i]
        i += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > len(data):
            break
        segment_len = struct.unpack(">H", data[i : i + 2])[0]
        if segment_len < 2 or i + segment_len > len(data):
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            if segment_len >= 7:
                height = struct.unpack(">H", data[i + 3 : i + 5])[0]
                width = struct.unpack(">H", data[i + 5 : i + 7])[0]
                return width, height
        i += segment_len
    return None


def image_size(path: Path) -> tuple[int, int]:
    size = png_size(path) if path.suffix.lower() == ".png" else jpeg_size(path)
    if not size:
        raise SystemExit(f"cannot read image dimensions: {path}")
    return size


def find_images(images_dir: Path) -> list[dict[str, Any]]:
    if not images_dir.is_dir():
        raise SystemExit(f"images directory not found: {images_dir}")
    paths = sorted(
        [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS],
        key=natural_key,
    )
    if not paths:
        raise SystemExit(f"no slide images found in: {images_dir}")
    records: list[dict[str, Any]] = []
    for path in paths:
        width, height = image_size(path)
        ratio = width / height
        records.append(
            {
                "path": str(path),
                "name": path.name,
                "width": width,
                "height": height,
                "ratio": ratio,
                "ratio_ok": abs(ratio - 16 / 9) <= 0.02,
            }
        )
    return records


def pptx_counts(pptx: Path) -> dict[str, int]:
    if not pptx.exists() or pptx.stat().st_size == 0:
        raise SystemExit(f"PPTX missing or empty: {pptx}")
    with zipfile.ZipFile(pptx) as zf:
        names = zf.namelist()
    slide_re = re.compile(r"^ppt/slides/slide\d+\.xml$")
    notes_re = re.compile(r"^ppt/notesSlides/notesSlide\d+\.xml$")
    media_re = re.compile(r"^ppt/media/")
    return {
        "slides": sum(1 for name in names if slide_re.match(name)),
        "notes": sum(1 for name in names if notes_re.match(name)),
        "media": sum(1 for name in names if media_re.match(name)),
    }


def extract_records(data: Any, label: str) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("slides", "records", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise SystemExit(f"{label} must be a list or contain a slides/records/items list")


def require_non_image2_approval(path: str | None) -> Path:
    if not path:
        raise SystemExit("--allow-non-image2 requires --non-image2-approval")
    approval_path = Path(path).expanduser().resolve()
    data = read_json(approval_path)
    if not isinstance(data, dict) or data.get("approved") is not True:
        raise SystemExit('non-Image2 approval file must contain {"approved": true}')
    return approval_path


def validate_manifest(
    manifest_path: Path,
    images: list[dict[str, Any]],
    allow_non_image2: bool,
    approval_path: Path | None,
) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    data = read_json(manifest_path)
    if not isinstance(data, dict):
        raise SystemExit("image_manifest.json must be a JSON object")

    route = str(data.get("image_route") or data.get("route") or "").strip()
    records = data.get("slides")
    if not isinstance(records, list):
        raise SystemExit("image_manifest.json must contain slides[]")

    route_ok = route in ALLOWED_ROUTES
    if not route_ok:
        if allow_non_image2 and approval_path:
            warnings.append(f"non-Image2 route approved: {route or '<empty>'}")
        else:
            errors.append(f"invalid image_route: {route or '<empty>'}")

    if not data.get("generated_at"):
        errors.append("image_manifest.json missing generated_at")
    if len(records) != len(images):
        errors.append(f"manifest slide count {len(records)} does not match image count {len(images)}")

    image_names = [image["name"] for image in images]
    slide_routes: list[str] = []
    capture_quality = {
        "codex_builtin_records": 0,
        "auto_select_newest": 0,
        "manual_source_image": 0,
        "generated_images_delta": 0,
    }
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"manifest slide {idx + 1} is not an object")
            continue
        slide_no = record.get("slide_number")
        if slide_no != idx + 1:
            errors.append(f"manifest slide {idx + 1} has slide_number={slide_no}")
        slide_route = str(record.get("image_route") or record.get("route") or route).strip()
        slide_routes.append(slide_route or "none")
        if slide_route not in ALLOWED_ROUTES:
            if allow_non_image2 and approval_path:
                warnings.append(f"slide {idx + 1} non-Image2 route approved: {slide_route or '<empty>'}")
            else:
                errors.append(f"slide {idx + 1} invalid image_route: {slide_route or '<empty>'}")
        image_value = record.get("image") or record.get("image_path") or record.get("workspace_image")
        if not image_value:
            errors.append(f"slide {idx + 1} missing image")
        elif idx < len(image_names) and Path(str(image_value)).name != image_names[idx]:
            errors.append(
                f"slide {idx + 1} manifest image {Path(str(image_value)).name} "
                f"does not match {image_names[idx]}"
            )
        if not record.get("prompt_ref"):
            errors.append(f"slide {idx + 1} missing prompt_ref")
        if not (record.get("source_generated_path") or record.get("generated_image_path") or record.get("provider_output_id")):
            errors.append(f"slide {idx + 1} missing source_generated_path/generated_image_path/provider_output_id")
        image_model = str(record.get("image_model") or record.get("model") or "").strip()
        if image_model != REQUIRED_IMAGE2_MODEL:
            errors.append(
                f"slide {idx + 1} image_model must be {REQUIRED_IMAGE2_MODEL}; got {image_model or '<empty>'}"
            )
        if slide_route == "tokenlane_image2":
            model_lock = str(record.get("model_lock") or image_model).strip()
            if model_lock != REQUIRED_IMAGE2_MODEL:
                errors.append(
                    f"slide {idx + 1} tokenlane_image2 model_lock must be {REQUIRED_IMAGE2_MODEL}; got {model_lock or '<empty>'}"
                )
        if slide_route == "codex_builtin_imagegen":
            capture_quality["codex_builtin_records"] += 1
            capture_method = str(record.get("capture_method") or "").strip()
            if capture_method not in {"generated_images_delta", "manual_source_image"}:
                errors.append(
                    f"slide {idx + 1} codex_builtin_imagegen missing valid capture_method"
                )
            else:
                capture_quality[capture_method] += 1
            if capture_method == "generated_images_delta" and not record.get("source_generated_path"):
                errors.append(
                    f"slide {idx + 1} generated_images_delta capture missing source_generated_path"
                )
            if not record.get("capture_root"):
                errors.append(f"slide {idx + 1} codex_builtin_imagegen missing capture_root")
            if not record.get("source_sha256"):
                errors.append(f"slide {idx + 1} codex_builtin_imagegen missing source_sha256")
            if not record.get("captured_at"):
                errors.append(f"slide {idx + 1} codex_builtin_imagegen missing captured_at")
            if str(record.get("selection_reason") or "").strip() == "auto_select_newest":
                capture_quality["auto_select_newest"] += 1
                warnings.append(f"slide {idx + 1} used auto_select_newest capture selection")
            if record.get("capture_candidate_count") is None:
                warnings.append(f"slide {idx + 1} codex_builtin_imagegen missing capture_candidate_count")
        status = str(record.get("generation_status") or "").strip().lower()
        if status not in GOOD_STATUSES:
            errors.append(f"slide {idx + 1} invalid generation_status: {status or '<empty>'}")

    summary = {
        "image_route": route or "none",
        "image_route_ok": route_ok,
        "manifest_slide_count": len(records),
        "slide_routes": slide_routes,
        "capture_quality": capture_quality,
    }
    return summary, errors, warnings


def validate_page_prompts(records: list[Any], image_count: int) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if len(records) != image_count:
        errors.append(f"page_prompts count {len(records)} does not match image count {image_count}")
        return errors, warnings
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"page_prompts slide {idx + 1} is not an object")
            continue
        page_text = str(record.get("page_text") or record.get("visible_text") or "").strip()
        content_density = str(record.get("content_density") or "").strip().lower()
        visualization_type = str(record.get("visualization_type") or "").strip().lower()
        text_risk_level = str(record.get("text_risk_level") or "").strip().lower()
        fallback_strategy = str(record.get("fallback_strategy") or "").strip()
        visible_items = record.get("visible_items")
        visual_brief = str(record.get("visual_brief") or "").strip()
        visual_format = str(record.get("visual_format") or "").strip()
        visual_metaphor = str(record.get("visual_metaphor") or "").strip()
        image_prompt = str(record.get("image_prompt") or "").strip()
        speaker_notes = str(record.get("speaker_notes") or record.get("notes") or "").strip()
        if not content_density:
            errors.append(f"page_prompts slide {idx + 1} missing content_density")
        elif content_density not in ALLOWED_DENSITY_VALUES:
            warnings.append(f"page_prompts slide {idx + 1} uses unrecognized content_density: {content_density}")
        if not visualization_type:
            errors.append(f"page_prompts slide {idx + 1} missing visualization_type")
        elif visualization_type not in ALLOWED_VISUALIZATION_TYPES:
            warnings.append(f"page_prompts slide {idx + 1} uses unrecognized visualization_type: {visualization_type}")
        if content_density in DENSE_DENSITY_VALUES and visualization_type not in DENSE_VISUALIZATION_TYPES:
            errors.append(
                f"page_prompts slide {idx + 1} is {content_density} but uses non-dense visualization_type: "
                f"{visualization_type or '<empty>'}"
            )
        if visible_items is None:
            errors.append(f"page_prompts slide {idx + 1} missing visible_items")
            visible_item_values: list[str] = []
        elif not isinstance(visible_items, list):
            errors.append(f"page_prompts slide {idx + 1} visible_items must be a list")
            visible_item_values = []
        else:
            visible_item_values = [str(item).strip() for item in visible_items if str(item).strip()]
        if content_density in DENSE_DENSITY_VALUES and not visible_item_values:
            errors.append(f"page_prompts slide {idx + 1} is {content_density} but visible_items is empty")
        if not text_risk_level:
            errors.append(f"page_prompts slide {idx + 1} missing text_risk_level")
        elif text_risk_level not in ALLOWED_TEXT_RISK_LEVELS:
            warnings.append(f"page_prompts slide {idx + 1} uses unrecognized text_risk_level: {text_risk_level}")
        if not fallback_strategy:
            errors.append(f"page_prompts slide {idx + 1} missing fallback_strategy")
        if not visual_brief:
            errors.append(f"page_prompts slide {idx + 1} missing visual_brief")
        if len(visual_brief) < 24:
            errors.append(f"page_prompts slide {idx + 1} visual_brief is too thin")
        if not visual_format:
            errors.append(f"page_prompts slide {idx + 1} missing visual_format")
        if not visual_metaphor:
            errors.append(f"page_prompts slide {idx + 1} missing visual_metaphor")
        if not image_prompt:
            errors.append(f"page_prompts slide {idx + 1} missing image_prompt")
        if page_text and visual_brief and visual_brief.replace(" ", "") in page_text.replace(" ", ""):
            errors.append(f"page_prompts slide {idx + 1} visual_brief only repeats visible text")
        lowered = f"{visual_brief}\n{image_prompt}".lower()
        structure_keywords = (
            "hierarchy",
            "group",
            "relationship",
            "compare",
            "matrix",
            "flow",
            "timeline",
            "metric",
            "infographic",
            "panel",
            "roadmap",
            "scorecard",
            "层级",
            "分组",
            "关系",
            "对比",
            "矩阵",
            "流程",
            "时间线",
            "指标",
            "信息图",
            "表格可视化",
            "分区",
            "路线图",
            "卡片",
        )
        has_structure = any(keyword in lowered for keyword in structure_keywords)
        if any(phrase in lowered for phrase in GENERIC_VISUAL_PHRASES) and not has_structure:
            errors.append(f"page_prompts slide {idx + 1} looks like a generic background prompt")
        if content_density in DENSE_DENSITY_VALUES and not has_structure:
            errors.append(f"page_prompts slide {idx + 1} is dense but visual_brief does not describe visual structure")
        if visible_item_values:
            missing_items = [item for item in visible_item_values if item not in image_prompt and item not in page_text]
            if missing_items:
                warnings.append(
                    f"page_prompts slide {idx + 1} visible_items not found in image_prompt/page_text: "
                    + ", ".join(missing_items[:6])
                )
            if len(visible_item_values) >= 6 and text_risk_level != "high":
                warnings.append(f"page_prompts slide {idx + 1} has many visible_items but text_risk_level is not high")
        if len(page_text) > 90 and len(speaker_notes) < len(page_text):
            warnings.append(f"page_prompts slide {idx + 1} has dense visible text without longer notes")
    return errors, warnings


def find_suspicious_local_rendering(deck_root: Path) -> list[str]:
    if not deck_root.exists():
        return []
    findings: list[str] = []
    for path in deck_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in {"build_image_deck.py", "validate_image_deck.py"}:
            continue
        if path.suffix.lower() not in {".py", ".html", ".js", ".mjs", ".svg"}:
            continue
        if path.name in {"montage.svg"} or "/rendered/" in path.as_posix():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern in text for pattern in SUSPICIOUS_SCRIPT_PATTERNS):
            findings.append(str(path))
    return findings


def main() -> int:
    args = parse_args()
    pptx = Path(args.pptx).expanduser().resolve()
    images_dir = Path(args.images_dir).expanduser().resolve()
    page_prompts_path = Path(args.page_prompts).expanduser().resolve()
    source_map_path = Path(args.source_map).expanduser().resolve()
    manifest_path = Path(args.image_manifest).expanduser().resolve()
    deck_root = Path(args.deck_root).expanduser().resolve() if args.deck_root else pptx.parent
    approval_path = require_non_image2_approval(args.non_image2_approval) if args.allow_non_image2 else None
    route_detection = detect_image_route(args.expected_route or "auto")
    expected_route = route_detection["image_route"]

    errors: list[str] = []
    warnings: list[str] = []
    deck_contract = validate_deck_contract(deck_root, errors)

    images = find_images(images_dir)
    counts = pptx_counts(pptx)
    prompts = extract_records(read_json(page_prompts_path), "page_prompts.json")
    source_records = extract_records(read_json(source_map_path), "source_map.json")
    manifest_summary, manifest_errors, manifest_warnings = validate_manifest(
        manifest_path,
        images,
        args.allow_non_image2,
        approval_path,
    )
    errors.extend(manifest_errors)
    warnings.extend(manifest_warnings)
    if expected_route and manifest_summary["image_route"] != expected_route:
        errors.append(
            f"image_route {manifest_summary['image_route']} does not match expected route {expected_route}"
        )
    if expected_route:
        bad_slide_routes = [
            f"{idx + 1}:{route}"
            for idx, route in enumerate(manifest_summary.get("slide_routes", []))
            if route != expected_route
        ]
        if bad_slide_routes:
            errors.append(
                "manifest slide routes do not match expected route "
                f"{expected_route}: " + ", ".join(bad_slide_routes[:12])
            )

    image_count = len(images)
    if counts["slides"] != image_count:
        errors.append(f"PPTX slide count {counts['slides']} does not match image count {image_count}")
    if counts["notes"] != image_count:
        errors.append(f"PPTX notesSlide count {counts['notes']} does not match image count {image_count}")
    prompt_errors, prompt_warnings = validate_page_prompts(prompts, image_count)
    errors.extend(prompt_errors)
    warnings.extend(prompt_warnings)
    if len(source_records) < image_count:
        errors.append(f"source_map count {len(source_records)} is less than image count {image_count}")

    non_16x9 = [image for image in images if not image["ratio_ok"]]
    if non_16x9 and not args.allow_non_16x9:
        errors.append(f"{len(non_16x9)} slide images are not 16:9")
    elif non_16x9:
        warnings.append(f"{len(non_16x9)} slide images are not 16:9")

    suspicious = find_suspicious_local_rendering(deck_root)
    if suspicious and not approval_path:
        errors.append("suspicious local rendering scripts found: " + ", ".join(suspicious))
    elif suspicious:
        warnings.append("suspicious local rendering scripts approved: " + ", ".join(suspicious))

    report = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "pptx": str(pptx),
        "deck_root": str(deck_root),
        "slide_count": counts["slides"],
        "notes_slide_count": counts["notes"],
        "pptx_media_count": counts["media"],
        "image_count": image_count,
        "all_images_16x9": not non_16x9,
        "non_16x9_images": non_16x9,
        "page_prompts_count": len(prompts),
        "source_map_count": len(source_records),
        "image_manifest_path": str(manifest_path),
        "image_route": manifest_summary["image_route"],
        "image_route_ok": manifest_summary["image_route_ok"],
        "expected_route": expected_route or None,
        "route_detection": route_detection,
        "slide_routes": manifest_summary["slide_routes"],
        "capture_quality": manifest_summary["capture_quality"],
        "authoring_valid": None,
        "deck_format_ok": deck_contract["deck_format_ok"],
        "deck_format": deck_contract["deck_format"],
        "native_editable_requested": deck_contract["native_editable_requested"],
        "pptx_backend_role": deck_contract["pptx_backend_role"],
        "deck_contract_path": deck_contract["path"],
        "prompt_quality_warnings": prompt_warnings,
        "image_manifest_slide_count": manifest_summary["manifest_slide_count"],
    }
    if args.qa_report:
        qa_path = Path(args.qa_report).expanduser().resolve()
        qa_path.parent.mkdir(parents=True, exist_ok=True)
        qa_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
