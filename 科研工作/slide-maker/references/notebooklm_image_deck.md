# NotebookLM-Style Image Decks

Use this reference for NotebookLM-style, full-image, visual-first, Apple/keynote, and Image2 decks.

## What "NotebookLM-like" Means

NotebookLM-style decks are visual explanations grounded in source material. They should feel like a narrated visual overview:

- source facts become visual objects, diagrams, quotes, timelines, maps, comparisons, or workflows;
- long detail moves to speaker notes and `source_map.json`;
- each slide has one visual teaching job;
- the sequence builds understanding instead of decorating paragraphs.

## Required Page Types

Choose one page type per slide:

- `big_idea`: one thesis or shift in thinking.
- `source_quote`: one short source-grounded quote or paraphrased evidence moment.
- `concept_map`: entities and relationships.
- `timeline`: sequence, milestones, phases.
- `comparison`: options, before/after, competing interpretations.
- `workflow`: actions, process, handoffs.
- `metrics`: 1-3 big numbers; no fake charts.
- `risk_next_step`: uncertainty, decision gate, next actions.
- `closing`: memorable landing message.

## Prompt Template

For each `page_prompts.json` record:

```json
{
  "slide_number": 1,
  "slide_job": "explain",
  "page_type": "concept_map",
  "content_density": "sparse|normal|dense|table_heavy|high_infographic",
  "page_text": "short visible text only",
  "visible_items": ["exact visible Chinese label"],
  "visual_format": "concept map with three labeled nodes",
  "visual_metaphor": "network opening from a teacher training hub to schools",
  "visual_brief": "human-readable design brief",
  "image_prompt": "final Image2 prompt assembled from style_spec + page content",
  "text_risk_level": "low|medium|high",
  "fallback_strategy": "reduce labels and regenerate with the same route",
  "speaker_notes": "source details, caveats, long explanation"
}
```

The `image_prompt` must include:

- canvas/aspect ratio;
- style lock from `style_spec.json`;
- exact visible text, kept short;
- page type and visual format;
- visual metaphor tied to the claim;
- layout and safe-text guidance;
- forbidden elements.

## Good Prompt Pattern

```text
16:9 full-slide visual explainer. Style: [style_spec visual_dna, palette, typography_mood].
Page type: concept map.
Visible text: [exact short title and labels].
Visual metaphor: [specific source-grounded metaphor].
Layout: [where title, main visual object, labels, quiet space go].
Rules: crisp Simplified Chinese text, no logos, no fake charts, no extra text, no dense paragraphs.
```

## Anti-Patterns

- "Make this NotebookLM style" with no page type or visual metaphor.
- Using Image2 as a background generator while overlaying a normal bullet slide.
- Asking the image model for dense tables, exact axes, full citations, logos, signatures, or small paragraphs.
- Repeating the same title + three cards layout across the deck.
- Letting unrelated source material appear because it was in the same document.

## QA Rubric

### Content

- The visible claim appears in `source_map.json`.
- The page teaches one idea.
- Unsupported or uncertain claims are in notes, not on the image.

### Design

- The page looks like a visual explanation, not a decorative background.
- The style matches `style_spec.json`.
- Text is large, readable, and sparse.
- Visual metaphors are source-specific.

### Coherence

- Slides share palette, typography mood, lighting, and diagram language.
- Each slide advances the story.
- Page types vary intentionally and do not repeat by habit.

## When Text Fails

If generated Chinese text is garbled or too small:

1. reduce visible text;
2. regenerate only that slide with the same style lock;
3. move detail into speaker notes;
4. do not switch to local deterministic full-slide rendering as a silent workaround;
5. if exact text is mission-critical, ask the user before switching to editable PPTX text or deterministic local rendering.

For default slide-maker decks, `image_route: none` means the image-deck requirement was not met unless the user explicitly approved that fallback before generation.

Run `scripts/validate_authoring.py` before generating images. The authoring artifacts must pass before using Image2; otherwise weak prompts, generic backgrounds, missing source maps, or unstructured dense pages will fail too late.
