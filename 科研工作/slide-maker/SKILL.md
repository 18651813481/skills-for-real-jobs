---
name: "slide maker"
description: "把资料、文字大纲或自然语言需求生成 PPTX，适合中文学术科研、组会、课程、讲座、论文解读、科研进展汇报和工作项目汇报。使用本技能时必须先把材料结构化提炼成大纲和证据映射，再选择最合适的风格。默认使用 Image2/gpt-image-2 对每页做整页视觉设计并封装为 image deck PPTX，不优先保证文字可编辑；只有用户明确要求可编辑时才输出原生可编辑 PPTX。"
---

# slide maker

Use this skill when the user wants to create, plan, polish, or QA a PowerPoint deck from sources, an outline, or a conversational brief. The default audience is Chinese academic and research work: paper interpretation, lab meeting, research progress, course lecture, academic news briefing, and seminar slides.

## Core Rules

- Default to an Image2/gpt-image-2 full-page image deck: every slide is designed as one full-bleed 16:9 image and wrapped in a `.pptx` container. Do not prioritize native text editability unless the user explicitly asks for an editable deck.
- For `source-to-deck`, always run the source analysis pipeline before writing slides: segment the material, identify relevant and excluded sections, extract claims/evidence/numbers/stakeholders/gaps, then create a structured outline. Do not turn source paragraphs directly into slides.
- For outline-to-deck or dense customer PPT redesign, do not pass the source text directly into slide images. First normalize each slide into `message_brief`, `content_density`, `visible_text`, `speaker_notes`, `visualization_type`, and `visual_brief`; then generate Image2 prompts from the visual brief. Dense outlines and PPT slides must be compressed into visual explanations; sparse outlines must be semantically expanded.
- In the default image deck mode, clearly report that visual quality is prioritized and slide text is not natively editable. If the user explicitly asks for NotebookLM-style, full-image, image deck, visual-first, or "全图像化" output, treat it as confirmation of the default Image2 route and be more aggressive with visual composition.
- A locally rendered full-slide PNG/JPG is not a substitute for Image2. Do not satisfy the default image-deck requirement by rendering HTML, SVG, canvas, matplotlib, PIL, PPT screenshots, or deterministic local layouts into images unless the user explicitly asks for deterministic rendering or editable/typographic precision over Image2 design.
- For default deck generation, `image_route: none` is a QA failure. Use `codex_builtin_imagegen` or `tokenlane_image2`, or stop and ask before producing a non-Image2 deck.
- Do not make any single visual style the global default. Follow the user's style prompt for the current deck; if no style is specified, infer the most suitable style from the source material, audience, purpose, and viewing context.
- If the current prompt explicitly asks for "Apple 发布会风格", "Apple keynote style", "发布会风格", "keynote", "premium launch", "视觉精致", or otherwise prioritizes cinematic/polished full-page visuals, treat that current deck as visual-first and use the NotebookLM-style image deck workflow with Image2/gpt-image-2 by default, unless the user explicitly says the slide text must remain natively editable. This is prompt-scoped and must not carry over to unrelated documents.
- Do not use screenshots, HTML, PDF, or a webpage as the main deliverable. The default deliverable is a `.pptx` image deck; use native editable `.pptx` only when the user explicitly asks for editable text/shapes/charts.
- Do not use NotebookLM or require a NotebookLM account.
- Use the best available PPTX authoring backend in this order:
  1. If an OpenAI `slides` skill is installed locally, use it for PptxGenJS authoring, rendering, and validation.
  2. Otherwise use the built-in `Presentations` plugin skill for PPTX creation, rendering, verification, and export.
  3. If neither route is available, use `scripts/build_image_deck.py` for image deck assembly when possible; otherwise stop and explain the missing deck authoring backend.
- For image assets, follow the Image Route Policy below. The route depends on Codex login mode and quota source, not merely on whether Tokenlane credentials exist.
- Do not use Image2 or any image generator for true data charts, axes, statistical figures, or factual scientific plots. Use deterministic tools, rendered chart images, or native PPT charts/tables for real data.
- Before generating a full deck from only a vague topic, ask for missing high-impact intent details unless the user asks to proceed directly. If they do not want to answer, default to an 8-slide Chinese academic clean image deck.
- Always render or otherwise verify the deck when tooling is available. Fix text overflow, overlap, clipping, missing images, and broken Chinese rendering before final delivery.

## Reference Files

Load these only when relevant:

- `references/content_pipeline.md`: required for `source-to-deck`, mixed documents, source-grounded decks, and any task where material must be summarized into an outline.
- `references/style_specs.md`: required when selecting a style, generating `style_spec.json`, or when the user has no explicit style prompt.
- `references/notebooklm_image_deck.md`: required for default Image2 image decks, NotebookLM-style, full-image, Apple/keynote, visual-first, or any Image2 whole-page deck.

## Request Classes

- `source-to-deck`: papers, PDFs, academic news, reports, Markdown, webpages, notes, transcripts, or source excerpts into a deck.
- `outline-to-deck`: user-provided title, sections, bullets, or page plan into structured slides.
- `chat-to-deck`: user asks in natural language and may want to discuss the deck before generation.
- `deck-polish`: user provides an existing `.pptx` and wants visual redesign, reflow, images, QA, narrative improvement, or conversion from text-heavy pages into Image2 visual explanations.
- `single-slide`: user wants one slide created or revised.
- `image-deck`: default route for any new deck unless the user explicitly asks for editable PPTX. Includes NotebookLM-like visual output, a whole deck as rendered pages, more effect images, all slides generated as Image2 visuals, or any style where polished full-page imagery matters more than native editability.

## Workflow

1. Classify the request class.
2. Determine goal, audience, slide count, tone, source material, image needs, and output constraints.
3. For `source-to-deck`, run the content pipeline and write authoring artifacts before any deck authoring:
   - `authoring/content_brief.json`
   - `authoring/deck_outline.json`
   - `authoring/source_map.json`
4. Choose and record the style:
   - If the user specified a style, follow it for this deck only.
   - If no style is specified, infer the most suitable style from source type, audience, purpose, and viewing context.
   - Write `authoring/style_spec.json` with the exact fields defined in `references/style_specs.md`.
5. Create a slide narrative before authoring:
   - thesis
   - audience shift
   - slide list
   - one job per slide
   - visual asset plan
   - QA plan
   - presentation intent: what the audience should understand, believe, compare, decide, or remember
   - visual explanation strategy: how images, spatial hierarchy, diagrams, scenes, and metaphors will teach the intent
6. Choose backend:
   - Prefer installed `slides` skill if present.
   - Otherwise use `Presentations`.
   - By default, skip editable-slide authoring as the main route and use Image2 plus `scripts/build_image_deck.py`; the PPTX backend is only the image container.
   - If the user explicitly asks for editable text/shapes/charts, use native editable PPTX authoring instead and state the tradeoff in visual freedom.
7. Generate or gather visual assets:
   - Select the route from the Image Route Policy.
   - Use the selected image route for PPT cover, section background, spot illustration, conceptual diagram, research poster, graphical abstract, or full-page image deck slides.
   - Copy final image assets into the deck workspace before insertion.
8. Author the deck:
   - Default mode: one 16:9 Image2-designed image per slide, then use `scripts/build_image_deck.py` to place images full-bleed into a PPTX container.
   - Explicit editable mode: native editable PPTX shapes, text, charts, and images.
9. Render and QA.
10. Run Content / Design / Coherence QA.
11. Return paths and a short status summary.

## Source-to-Deck Rules

- Load `references/content_pipeline.md`.
- Extract claims, evidence, methods, limitations, and narrative, not raw paragraphs.
- Preserve source-grounding: do not invent findings, numeric results, author claims, or citations.
- Before writing the outline, explicitly classify sections as `included_sections`, `excluded_sections`, or `uncertain_sections`. For mixed documents, do not include unrelated sections merely because they appear in the same file.
- Write `content_brief.json` with: `source_scope`, `included_sections`, `excluded_sections`, `core_questions`, `key_facts`, `usable_numbers`, `stakeholders`, `conflicts_or_gaps`, and `recommended_deck_angle`.
- Write `deck_outline.json` with: `thesis`, `audience_shift`, `slide_count`, and one record per slide containing `slide_number`, `slide_job`, `main_message`, `evidence_refs`, `recommended_visual_form`, and `speaker_notes`.
- Write or update `source_map.json` with one record per slide. Each slide claim must be marked `source-grounded`, `inferred`, or `unsupported`. Remove unsupported claims from visible slide text unless the user explicitly wants a concept draft.
- Convert dense source content into diagrams, timelines, comparisons, charts, tables, or speaker notes.
- Put detailed caveats, methodology, and long references into speaker notes or appendix slides when needed.
- Each non-appendix slide gets exactly one job: explain, compare, show evidence, show process, show timeline, identify risk, support a decision, give next actions, or close.
- For recent academic news or public facts, verify with current sources before using.

## Outline-to-Deck Rules

- Preserve the user's hierarchy, but do not mechanically make one bullet into one slide.
- Detect sections, nested bullets, chronology, contrast, cause-effect, and evidence groups.
- Every slide must have one slide job, such as cover, agenda, problem, method, finding, evidence, workflow, comparison, implication, summary, Q&A, or appendix.
- If a bullet list is too dense, split it or convert it into a process, matrix, timeline, table, or speaker notes. Do not switch to local deterministic rendering just because the outline has too much Chinese text.
- If the outline is sparse, infer the missing visual logic from the slide job, audience, deck thesis, adjacent slides, and style spec. Expand into a concrete `visual_brief` and `visual_metaphor`; do not produce a generic background with only the provided short text.
- Keep Chinese academic wording rigorous, but reduce slide text to presentation-safe phrasing.
- For every slide, write the normalized fields before image generation:
  - `message_brief`: one sentence explaining what the slide must make the audience understand.
  - `content_density`: `sparse`, `normal`, `dense`, or `table_heavy`.
  - `visible_text`: one large title plus at most one subtitle, 2-4 labels, or 1-3 big numbers.
  - `speaker_notes`: the detailed original outline content and caveats.
  - `visualization_type`: one concrete form such as `infographic`, `comparison_matrix`, `workflow`, `timeline`, `metrics_card`, `table_visualization`, `risk_map`, or `concept_map`.
  - `visual_brief`: a specific scene, diagram, workflow, comparison, metaphor, or evidence view that teaches the message.

## Dense PPT Redesign Rules

Use these rules when a customer provides a `.pptx`, PDF, Word brief, or outline with too much visible text, many bullet pages, or tables.

- Treat the original deck as source material, not as a layout template to preserve. Extract each page's intended message, supporting details, table structure, and decision purpose before designing.
- Do not solve dense Chinese text by switching to local deterministic rendering or editable text-first PPT. Keep the default Image2 image deck route and reduce visible text.
- For each dense slide, choose one transformation:
  - `compress`: keep one message and move detail to notes.
  - `split`: divide one overloaded page into 2-3 visual pages.
  - `merge`: combine repeated pages into one overview.
  - `appendix`: move detail-heavy reference material out of the main story.
- Convert dense content into Image2 visual forms:
  - bullet-heavy pages -> infographic, concept map, workflow, decision tree, or risk map;
  - text comparisons -> comparison matrix, before/after, quadrant, or option cards;
  - schedules and phases -> timeline, roadmap, swimlane, or milestone map;
  - tables -> table visualization, heatmap-like matrix, scorecard, grouped cards, or annotated grid;
  - numbers -> metrics cards or 1-3 large number callouts, not exact plotted charts.
- Preserve exact source text, table values, caveats, and citations in `speaker_notes` and `source_map.json`. The Image2 page should communicate the pattern, hierarchy, contrast, flow, or decision meaning, not reproduce every cell.
- If a table or chart requires exact axes, exact values, or audit-grade fidelity, create a deterministic chart/table asset only as a factual insert or notes artifact; do not use that as a full-slide local rendering substitute for Image2.

## Chat-to-Deck Rules

If the user only gives a topic, ask up to six high-impact questions:

1. Purpose: lab meeting, course, defense, academic news, project update, or public lecture.
2. Audience: undergraduate, graduate, PI, peer researchers, or non-specialists.
3. Length: short 3-5, standard 8-12, or long 15+ slides.
4. Style: academic clean, premium tech, teaching/explainer, practical lab meeting, or formal defense.
5. Sources: provided files, pasted text, web links, or no source material.
6. Images: cover only, several illustrations, diagrams, or no AI images.

If the user says to proceed without answering, default to:

- Chinese language.
- 8 slides.
- Academic clean style.
- Image2 full-page image deck wrapped as `.pptx`.
- Short visible text, with details in speaker notes and authoring artifacts.
- Deterministic source artifacts for factual data; avoid asking Image2 to invent exact charts.

## NotebookLM-Style Image Deck Rules

Load `references/notebooklm_image_deck.md` and `references/style_specs.md`.

Use this mode by default for new deck generation. The goal is to approximate NotebookLM's polished raster-slide look, or the user's requested visual language, while keeping source-grounding and local file control. The visual style itself is not global: Apple/keynote, NotebookLM, academic clean, formal report, and other styles are still selected per prompt and source.

NotebookLM-like intelligence requirement:

- Treat source material, outlines, or brief text as raw material, not as slide copy.
- First infer the presentation intent: audience, purpose, decision context, narrative arc, and what each slide must make clearer.
- Then redesign each slide as a visual explanation: choose a page type, visual metaphor, spatial structure, key objects, relationships, and emotional tone.
- If the input is long, synthesize and compress; if the input is short, infer the missing visual logic and enrich it from the deck thesis and adjacent slides.
- Never make a normal text layout and then decorate it. Every Image2 prompt must describe the designed visual argument, not just the words to place on a slide.

Default Image2 image deck behavior:

- Use Image2 for every slide as a full-page 16:9 composition, not only for cover or background accents.
- Keep page text extremely short: one large title plus at most one subtitle, 2-4 labels, or 1-3 big numbers.
- Let Image2 handle the whole page design: composition, lighting, diagram language, spatial hierarchy, illustration, and visual metaphor.
- Do not constrain the deck around native text editability; preserve source detail in speaker notes and authoring artifacts.
- Do not replace Image2 with local deterministic rendering to improve Chinese text accuracy. First reduce visible text and regenerate with Image2; if exact text is mission-critical, ask the user before switching to editable/local rendering.

Prompt-scoped Apple/keynote-style behavior:

- Prefer cinematic stage lighting, deep negative space, premium product-launch pacing, refined glass/light objects, and consistent style locks across slides.
- Avoid dense paragraphs, footnotes, stock corporate card grids, editable-text-first layouts, and generic presentation templates.
- State in the final response that the deck is image-based and slide text is not natively editable.

Required authoring artifacts:

- `authoring/content_brief.json`: material scope, included/excluded sections, key facts, numbers, stakeholders, conflicts/gaps, and recommended deck angle.
- `authoring/deck_outline.json`: thesis, audience shift, slide list, evidence refs, visual forms, and notes.
- `authoring/style_spec.json`: style route and exact visual system for the current deck.
- `authoring/slide_narrative.md`: human-readable slide list, thesis, audience shift, one job per slide, and revision notes.
- `authoring/page_prompts.json`: one record per slide with `slide_number`, `slide_job`, `page_type`, `content_density`, `message_brief`, `page_text`, `visualization_type`, `visual_format`, `visual_metaphor`, `visual_brief`, `image_prompt`, and `speaker_notes`.
- `authoring/image_manifest.json`: one record per generated slide image proving the actual Image2 route, copied image path, original generated image path, and prompt reference. This file is mandatory for default image decks.
- `authoring/source_map.json`: source chunks or file sections used by each slide, plus caveats and evidence status.

Page planning rules:

- Keep page text short. Image models are unreliable with dense small text, so use large titles, short labels, and visual hierarchy.
- Put factual detail, caveats, references, and long bullets into speaker notes and `source_map.json`, not into the image prompt.
- Compose each image prompt from `slide_job + page_text + visual_format + visual_metaphor + layout_grammar + style_spec`. Do not prompt with only a generic style phrase such as "NotebookLM style" or "Apple style".
- For every slide, `visual_brief` must answer: what is being explained, what visual object or scene carries the explanation, how the audience's understanding changes, and why this visual fits the report context.
- The image prompt must include both semantic expansion and text reduction:
  - Dense input: compress visible text, move the rest to notes, and ask Image2 for a visual explanation of the condensed message.
  - Sparse input: expand the meaning into concrete visual objects, relationships, spatial hierarchy, and scene details based on audience and deck narrative.
- For dense or table-heavy source pages, the prompt must explicitly name the intended `visualization_type` and describe how bullets or table cells become hierarchy, groups, relationships, comparisons, flow, or metrics.
- Use fixed page types where possible: `big_idea`, `source_quote`, `concept_map`, `timeline`, `comparison`, `workflow`, `metrics`, `risk_next_step`, and `closing`.
- Do not ask Image2 to fabricate statistical charts, axes, exact tables, logos, signatures, citations, or precise numeric plots. Use conceptual visuals for those pages, and preserve exact facts in notes.
- Use a shared style lock after the first 1-2 pages: visual language, palette, typography mood, lighting, margin style, and icon/diagram treatment. Reuse it in every page prompt to reduce style drift.
- For academic decks, include evidence/method, limitation, and source appendix pages when source material supports them.

Image generation rules:

- Prefer Image2 with custom 16:9 sizes such as `1536x864` or another legal 16:9 `WIDTHxHEIGHT` accepted by Image2.
- Use `--quality high` for cover and important visual pages when budget allows.
- Use `--filename-prefix` with zero-padded slide numbers, for example `slide-01`, `slide-02`.
- Save Image2 manifests next to the images; do not include API keys, Authorization headers, or raw `b64_json` in authoring files.
- For built-in membership mode, after every `image_gen` generation, copy the selected generated file into `images/slide-XX.png` and append a matching `authoring/image_manifest.json` record with `image_route: "codex_builtin_imagegen"`.
- Built-in membership `image_gen` is a conversational tool, so long decks must be generated in small resumable batches. Membership mode still uses member `image_gen`; do not switch membership mode to Tokenlane/API to improve stability.
- For Tokenlane/API mode, use the Tokenlane script output manifest and normalize it into `authoring/image_manifest.json` with `image_route: "tokenlane_image2"`.
- Tokenlane/API generation is used only in non-membership/API-login contexts. Do not call Tokenlane merely because a member-login `image_gen` run is slow or times out.
- Never create or run a local full-slide rendering script as a substitute for Image2. A Python/PIL, SVG, HTML/canvas, matplotlib, or PPT screenshot generator may only be used for deterministic source charts or explicit user-approved fallback, not for the default slide page images.

Assembly command:

```bash
python3 /path/to/slide-maker/scripts/build_image_deck.py \
  --images-dir "/absolute/path/to/workspace/images" \
  --output "/absolute/path/to/workspace/deck_image-deck.pptx" \
  --title "Deck title" \
  --notes-json "/absolute/path/to/workspace/authoring/page_prompts.json" \
  --image-manifest "/absolute/path/to/workspace/authoring/image_manifest.json" \
  --source-map "/absolute/path/to/workspace/authoring/source_map.json" \
  --montage "/absolute/path/to/workspace/rendered/montage.svg"
```

The assembly script must fail if `--image-manifest` is missing or if the manifest route is not `codex_builtin_imagegen` or `tokenlane_image2`. Use `--allow-non-image2` only after the user explicitly approves a non-Image2 fallback.

Final validation command:

```bash
python3 /path/to/slide-maker/scripts/validate_image_deck.py \
  --pptx "/absolute/path/to/workspace/deck_image-deck.pptx" \
  --images-dir "/absolute/path/to/workspace/images" \
  --page-prompts "/absolute/path/to/workspace/authoring/page_prompts.json" \
  --source-map "/absolute/path/to/workspace/authoring/source_map.json" \
  --image-manifest "/absolute/path/to/workspace/authoring/image_manifest.json" \
  --qa-report "/absolute/path/to/workspace/qa-report.json"
```

Do not deliver a default image deck unless `validate_image_deck.py` exits successfully and the QA report has `valid: true` and `image_route_ok: true`.

Revision rules:

- For a single-slide revision, regenerate only that slide image with the same style lock and update the corresponding `page_prompts.json` record.
- Rebuild the image deck after replacing the image file. Do not regenerate unaffected slide images unless the user asks for a full restyle.
- If a factual claim changes, update `source_map.json` and speaker notes before rebuilding the PPTX.

## Image Route Policy

Choose the Image2 route from Codex login mode and quota source. Task size does not change the billing route:

1. If Codex is logged in with normal ChatGPT/Codex membership (`~/.codex/auth.json` has `auth_mode: "chatgpt"` and no active `OPENAI_API_KEY`), always use built-in membership `imagegen` / `image_gen`. Record `image_route: "codex_builtin_imagegen"`.
2. Only if Codex is in non-membership/API-login mode, or otherwise explicitly configured for API usage, use Tokenlane Image2 by running `/Users/fly/.codex/skills/Image2/scripts/generate_image.py`. Record `image_route: "tokenlane_image2"`.
3. If the required route is unavailable, stop and report the route problem. Do not switch to the other billing route and do not switch to local rendering.

Membership timeout mitigation:

- Do not run a long, uninterrupted 10-30 slide membership `image_gen` sequence in one fragile chain. In membership mode, work from `page_prompts.json` in small batches of 1-3 slides, copy outputs into the deck workspace, update `image_manifest.json`, and stop/resume from the first missing `slide-XX.png` when needed.
- Keep each Image2 prompt concise: include the slide's intent, visible text, page type, visual metaphor, style lock, and forbidden patterns; keep long source notes out of the image prompt.
- If membership `image_gen` times out, do not switch to Tokenlane/API and do not switch to local rendering. Resume the missing slides with the same membership route, or stop and report the upstream timeout.

Tokenlane Image2 is the default only for non-membership/API-login/API-key contexts. The Image2 script resolves Tokenlane keys in this order:

1. `TOKENLANE_API_KEY`
2. `IMAGE2_API_KEY`
3. `~/.codex/Image2/api_key`
4. `~/.codex/Image2/config.json`
5. `~/.codex/auth.json` only when `~/.codex/config.toml` contains `api.tokenlane.tech`

Recommended Image2 presets:

- `ppt-cover`: cover background or hero visual.
- `ppt-section`: section divider background.
- `ppt-illustration`: content slide illustration.
- `ppt-diagram`: conceptual diagram, not real data visualization.
- `research-poster`: academic poster visual.
- `graphical-abstract`: scientific concept visual.

In built-in membership mode, copy selected generated images from Codex's generated image location into the deck workspace before insertion. Never leave project-bound slide images only in the default generated-images location.

Record the actual image path and `image_route` in the final response:

- `tokenlane_image2`
- `codex_builtin_imagegen`
- `none` only when the user explicitly approved a non-Image2 fallback or every Image2 route failed after being attempted and reported.

## QA Requirements

At minimum, check:

- `.pptx` exists and is non-empty.
- PPTX package can be inspected or unzipped.
- Slide count matches the requested plan.
- `authoring/image_manifest.json` exists and has one record per slide image.
- `validate_image_deck.py` exits successfully and writes `valid: true`.
- Rendered PNG previews exist when rendering tooling is available.
- Chinese text is not garbled.
- No text overflow, clipped titles, bottom cropping, or unreadable small labels.
- No overlapping text or images.
- AI images are clear enough and not used as fake data charts.
- Default image decks must have `image_route` equal to `tokenlane_image2` or `codex_builtin_imagegen`; `none` fails QA unless the user explicitly approved a non-Image2 fallback before generation. The QA report must include `image_route`, `image_route_ok`, and `image_manifest_path`.
- `page_prompts.json` must show that dense outline text was compressed and sparse outline text was expanded into a concrete visual brief; prompts that only repeat user bullets or only ask for a generic background fail QA.
- For dense PPT redesign, `page_prompts.json` must mark dense/table-heavy pages with `content_density` and a concrete `visualization_type`; dense source pages without an infographic, matrix, workflow, timeline, metrics card, concept map, or table visualization fail QA.
- For default image decks, verify that slide count equals image count and narrative page count, every image is 16:9, the montage exists, and the final response says the deck is image-based rather than text-editable.
- For explicit editable decks, verify that native text, shapes, charts, and tables remain editable where appropriate.
- For source-grounded decks, verify that `source_map.json` covers the main claims and that unsupported claims are removed or marked as concept draft.
- Run a lightweight rubric:
  - Content: source-grounded claims, clear thesis, relevant included sections, no unrelated source cargo.
  - Design: follows `style_spec.json`, uses visual explanation rather than decorative background-only pages, avoids forbidden patterns.
  - Coherence: consistent visual system, meaningful slide progression, no repeated slide jobs unless intentional.

Final response should include:

- PPTX path.
- Authoring source paths when available: `content_brief.json`, `deck_outline.json`, `style_spec.json`, `slide_narrative.md`, `source_map.json`, and `page_prompts.json`.
- `image_manifest.json` path and actual `image_route`.
- Rendered slide preview path or directory when available.
- Montage path when available.
- Image asset path and route.
- For image deck mode, state that the deck is image-based and slide text is not natively editable.
- QA result summary.
- Any unresolved limitations.

## Failure Handling

- If official `slides` skill is unavailable, use `Presentations` and report that OpenAI curated slides was not available locally.
- If Image2 fails but built-in image generation is available, use built-in image generation.
- If both image routes fail, ask before producing the deck without AI images. Do not silently switch to deterministic local rendering for the main deck.
- If source material is insufficient for factual claims, ask for the source or mark the deck as a concept draft.
- If the user requests NotebookLM specifically, explain that this workflow avoids NotebookLM and stays in Codex.
