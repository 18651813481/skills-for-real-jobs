#!/usr/bin/env python3
"""Validate slide-maker authoring artifacts before image generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_CONTENT_BRIEF = {
    "source_scope",
    "included_sections",
    "excluded_sections",
    "core_questions",
    "key_facts",
    "usable_numbers",
    "stakeholders",
    "conflicts_or_gaps",
    "recommended_deck_angle",
}
REQUIRED_STYLE_SPEC = {
    "style_name",
    "format",
    "visual_dna",
    "palette",
    "typography_mood",
    "layout_grammar",
    "page_roles",
    "image_prompt_rules",
    "forbidden_patterns",
}
ALLOWED_DENSITY_VALUES = {"sparse", "normal", "dense", "table_heavy", "high_infographic"}
ALLOWED_TEXT_RISK_LEVELS = {"low", "medium", "high"}
DENSE_DENSITY_VALUES = {"dense", "table_heavy", "high_infographic"}
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
GENERIC_VISUAL_PHRASES = {
    "background",
    "背景",
    "科技背景",
    "abstract background",
    "generic",
    "简单背景",
    "纯背景",
}
STRUCTURE_KEYWORDS = {
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
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate slide-maker authoring artifacts.")
    parser.add_argument("--workspace", required=True, help="Deck workspace root.")
    parser.add_argument("--content-brief", help="Defaults to <workspace>/authoring/content_brief.json.")
    parser.add_argument("--deck-outline", help="Defaults to <workspace>/authoring/deck_outline.json.")
    parser.add_argument("--style-spec", help="Defaults to <workspace>/authoring/style_spec.json.")
    parser.add_argument("--page-prompts", help="Defaults to <workspace>/authoring/page_prompts.json.")
    parser.add_argument("--source-map", help="Defaults to <workspace>/authoring/source_map.json.")
    parser.add_argument("--report", help="Optional JSON report path.")
    return parser.parse_args()


def read_json(path: Path, errors: list[str], label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} not found: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
    return None


def records_from(data: Any, label: str, errors: list[str]) -> list[dict[str, Any]]:
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict) and isinstance(data.get("slides"), list):
        raw = data["slides"]
    elif isinstance(data, dict) and isinstance(data.get("records"), list):
        raw = data["records"]
    else:
        errors.append(f"{label} must be a list or contain slides[]/records[]")
        return []
    records: list[dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(f"{label} record {idx} must be an object")
            continue
        records.append(item)
    return records


def has_structure(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in STRUCTURE_KEYWORDS)


def validate_content_brief(data: Any, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("content_brief.json must be an object")
        return
    missing = sorted(REQUIRED_CONTENT_BRIEF - set(data))
    if missing:
        errors.append("content_brief.json missing fields: " + ", ".join(missing))
    for key in ("included_sections", "excluded_sections", "core_questions", "key_facts"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"content_brief.json {key} must be a list")


def validate_style_spec(data: Any, errors: list[str]) -> None:
    if not isinstance(data, dict):
        errors.append("style_spec.json must be an object")
        return
    missing = sorted(REQUIRED_STYLE_SPEC - set(data))
    if missing:
        errors.append("style_spec.json missing fields: " + ", ".join(missing))
    if data.get("format") not in {"image_deck", "editable_pptx"}:
        errors.append("style_spec.json format must be image_deck or editable_pptx")
    for key in ("visual_dna", "layout_grammar", "image_prompt_rules", "forbidden_patterns"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"style_spec.json {key} must be a list")
    if not isinstance(data.get("palette"), dict):
        errors.append("style_spec.json palette must be an object")
    if not isinstance(data.get("page_roles"), dict):
        errors.append("style_spec.json page_roles must be an object")


def validate_deck_outline(data: Any, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        errors.append("deck_outline.json must be an object")
        return []
    for key in ("thesis", "audience_shift", "slide_count", "slides"):
        if key not in data:
            errors.append(f"deck_outline.json missing {key}")
    slides = records_from(data, "deck_outline.json", errors) if "slides" in data else []
    if isinstance(data.get("slide_count"), int) and data["slide_count"] != len(slides):
        errors.append(f"deck_outline slide_count {data['slide_count']} does not match slides length {len(slides)}")
    for idx, slide in enumerate(slides, start=1):
        for key in ("slide_number", "slide_job", "main_message", "evidence_refs", "recommended_visual_form", "speaker_notes"):
            if key not in slide:
                errors.append(f"deck_outline slide {idx} missing {key}")
        if slide.get("slide_number") != idx:
            errors.append(f"deck_outline slide {idx} has slide_number={slide.get('slide_number')}")
        if "evidence_refs" in slide and not isinstance(slide["evidence_refs"], list):
            errors.append(f"deck_outline slide {idx} evidence_refs must be a list")
    return slides


def validate_source_map(data: Any, slide_count: int, errors: list[str]) -> list[dict[str, Any]]:
    records = records_from(data, "source_map.json", errors)
    if len(records) < slide_count:
        errors.append(f"source_map count {len(records)} is less than slide count {slide_count}")
    for idx, record in enumerate(records, start=1):
        if not any(key in record for key in ("claim", "claims", "source_refs", "sources", "evidence_status")):
            errors.append(f"source_map record {idx} lacks claim/source/evidence fields")
    return records


def validate_page_prompts(data: Any, slide_count: int, errors: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    records = records_from(data, "page_prompts.json", errors)
    if len(records) != slide_count:
        errors.append(f"page_prompts count {len(records)} does not match slide count {slide_count}")
    for idx, record in enumerate(records, start=1):
        if record.get("slide_number") != idx:
            errors.append(f"page_prompts slide {idx} has slide_number={record.get('slide_number')}")
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

        for key in ("slide_job", "page_type", "message_brief", "page_text", "visual_format", "visual_metaphor", "visual_brief", "image_prompt", "speaker_notes"):
            if not str(record.get(key) or "").strip():
                errors.append(f"page_prompts slide {idx} missing {key}")
        if content_density not in ALLOWED_DENSITY_VALUES:
            errors.append(f"page_prompts slide {idx} invalid content_density: {content_density or '<empty>'}")
        if visualization_type not in ALLOWED_VISUALIZATION_TYPES:
            errors.append(f"page_prompts slide {idx} invalid visualization_type: {visualization_type or '<empty>'}")
        if content_density in DENSE_DENSITY_VALUES and visualization_type not in DENSE_VISUALIZATION_TYPES:
            errors.append(f"page_prompts slide {idx} is {content_density} but visualization_type is {visualization_type}")
        if not isinstance(visible_items, list):
            errors.append(f"page_prompts slide {idx} visible_items must be a list")
            visible_values: list[str] = []
        else:
            visible_values = [str(item).strip() for item in visible_items if str(item).strip()]
        if content_density in DENSE_DENSITY_VALUES and not visible_values:
            errors.append(f"page_prompts slide {idx} is {content_density} but visible_items is empty")
        if text_risk_level not in ALLOWED_TEXT_RISK_LEVELS:
            errors.append(f"page_prompts slide {idx} invalid text_risk_level: {text_risk_level or '<empty>'}")
        if not fallback_strategy:
            errors.append(f"page_prompts slide {idx} missing fallback_strategy")
        if len(visual_brief) < 24:
            errors.append(f"page_prompts slide {idx} visual_brief is too thin")
        if page_text and visual_brief and visual_brief.replace(" ", "") in page_text.replace(" ", ""):
            errors.append(f"page_prompts slide {idx} visual_brief only repeats visible text")
        combined = f"{visual_format}\n{visual_metaphor}\n{visual_brief}\n{image_prompt}"
        if any(phrase in combined.lower() for phrase in GENERIC_VISUAL_PHRASES) and not has_structure(combined):
            errors.append(f"page_prompts slide {idx} looks like a generic background prompt")
        if content_density in DENSE_DENSITY_VALUES and not has_structure(combined):
            errors.append(f"page_prompts slide {idx} is dense but lacks visual structure")
        if content_density == "sparse" and (len(visual_brief) < 50 or not has_structure(combined)):
            errors.append(f"page_prompts slide {idx} is sparse but lacks semantic visual expansion")
        if visible_values:
            missing = [item for item in visible_values if item not in image_prompt and item not in page_text]
            if missing:
                warnings.append(f"page_prompts slide {idx} visible_items not found in prompt/text: " + ", ".join(missing[:6]))
    return records


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    authoring = workspace / "authoring"
    paths = {
        "content_brief": Path(args.content_brief).expanduser().resolve() if args.content_brief else authoring / "content_brief.json",
        "deck_outline": Path(args.deck_outline).expanduser().resolve() if args.deck_outline else authoring / "deck_outline.json",
        "style_spec": Path(args.style_spec).expanduser().resolve() if args.style_spec else authoring / "style_spec.json",
        "page_prompts": Path(args.page_prompts).expanduser().resolve() if args.page_prompts else authoring / "page_prompts.json",
        "source_map": Path(args.source_map).expanduser().resolve() if args.source_map else authoring / "source_map.json",
    }
    errors: list[str] = []
    warnings: list[str] = []
    content_brief = read_json(paths["content_brief"], errors, "content_brief.json")
    deck_outline = read_json(paths["deck_outline"], errors, "deck_outline.json")
    style_spec = read_json(paths["style_spec"], errors, "style_spec.json")
    page_prompts = read_json(paths["page_prompts"], errors, "page_prompts.json")
    source_map = read_json(paths["source_map"], errors, "source_map.json")

    if content_brief is not None:
        validate_content_brief(content_brief, errors)
    if style_spec is not None:
        validate_style_spec(style_spec, errors)
    outline_slides = validate_deck_outline(deck_outline, errors) if deck_outline is not None else []
    slide_count = len(outline_slides)
    if page_prompts is not None:
        validate_page_prompts(page_prompts, slide_count, errors, warnings)
    if source_map is not None:
        validate_source_map(source_map, slide_count, errors)

    report = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "workspace": str(workspace),
        "paths": {key: str(path) for key, path in paths.items()},
        "slide_count": slide_count,
    }
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
