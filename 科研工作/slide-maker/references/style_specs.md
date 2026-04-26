# Style Specs

Use this reference whenever choosing or recording a deck style.

## Routing Rules

- If the user names a style, follow it for the current deck only.
- If no style is specified, infer from source, audience, and use:
  - formal work/project material -> `formal_work_report`
  - academic paper/research -> `academic_clean`
  - lecture/course/explainer -> `teaching_explainer`
  - product/technology launch -> `keynote_launch`
  - visual-first source explanation -> `notebooklm_visual_explainer`
  - strategy/market narrative -> `magazine_infographic`
  - brainstorming or rough concept -> `whiteboard_explainer`
- Never make one style the global default across unrelated documents.

## `style_spec.json`

Always use these fields.

```json
{
  "style_name": "notebooklm_visual_explainer",
  "format": "editable_pptx|image_deck",
  "visual_dna": ["short descriptors of the visual language"],
  "palette": {
    "background": "description or hex family",
    "primary": "description or hex family",
    "accent": ["accent descriptions or hex families"]
  },
  "typography_mood": "modern Chinese sans, editorial serif, classroom marker, etc.",
  "layout_grammar": [
    "recurring composition rules, not generic template names"
  ],
  "page_roles": {
    "cover": "how covers behave",
    "evidence": "how evidence pages behave",
    "workflow": "how process pages behave",
    "closing": "how closing pages behave"
  },
  "image_prompt_rules": [
    "rules that every image prompt must follow"
  ],
  "forbidden_patterns": [
    "things that would make this deck feel wrong"
  ]
}
```

## Built-In Style Library

### `notebooklm_visual_explainer`

- Format: default `image_deck`.
- Visual DNA: editorial educational explainer, source-grounded visual metaphors, diagrams that teach, clean labels, documentary clarity.
- Layout grammar: one dominant idea, one visual explanation object, minimal labels, clear hierarchy, source details in notes.
- Forbidden patterns: generic dark tech backgrounds, dense paragraph slides, decorative images unrelated to the claim, fake data charts.

### `keynote_launch`

- Format: default `image_deck`.
- Visual DNA: cinematic stage, deep negative space, refined glow, product-launch pacing, monumental type.
- Layout grammar: big reveal, metric reveal, elegant architecture diagram, dramatic closing.
- Forbidden patterns: corporate card grids, busy dashboards, small footnotes, generic Apple logo imitation, style carrying over to unrelated decks.

### `academic_clean`

- Format: default `image_deck`; use `editable_pptx` only when the user explicitly asks for native editability.
- Visual DNA: precise, restrained, citation-aware, calm.
- Layout grammar: claim + evidence, method diagrams, readable charts/tables, appendix for density.
- Forbidden patterns: invented visuals, vague claims, over-stylized backgrounds that reduce trust.

### `formal_work_report`

- Format: default `image_deck`; use `editable_pptx` only when the user explicitly asks for native editability.
- Visual DNA: structured, decision-oriented, restrained visual hierarchy.
- Layout grammar: issue, evidence, option, risk, next action.
- Forbidden patterns: playful tone, cinematic excess, text-heavy source dumps.

### `teaching_explainer`

- Format: default `image_deck`; use `editable_pptx` only when the user explicitly asks for native editability.
- Visual DNA: friendly, stepwise, clear mental models.
- Layout grammar: concept introduction, example, guided diagram, recap.
- Forbidden patterns: executive consulting templates, unexplained jargon, overloaded diagrams.

### `whiteboard_explainer`

- Format: default `image_deck`; use `editable_pptx` only when the user explicitly asks for native editability.
- Visual DNA: sketch-like clarity, hand-drawn logic, simple arrows.
- Layout grammar: problem -> mechanism -> implication.
- Forbidden patterns: polished marketing look, tiny labels, complex dashboards.

### `magazine_infographic`

- Format: default `image_deck`; use `editable_pptx` only when the user explicitly asks for native editability.
- Visual DNA: editorial hierarchy, strong facts, charts and callouts.
- Layout grammar: headline, visual evidence, annotated detail.
- Forbidden patterns: stock template grids, unsupported statistics, decorative-only art.

## Prompt Quality Rule

The style spec is not decoration. Every slide prompt must combine:

`slide_job + page_text + visual_format + visual_metaphor + layout_grammar + style_spec + forbidden_patterns`.
