# Customer PPT Polish SOP

Use this reference when redesigning an existing customer-facing PPT, business proposal, exhibition-hall concept deck, formal report, or dense text deck. The goal is not to make a prettier template; it is to turn source material into a coherent, premium, readable presentation that a colleague can continue to produce at the same quality level.

## Success Standard

A successful customer PPT polish should meet all of these:

- The source deck's visible meaning is preserved. Titles, section names, body copy, table values, and client-specific wording are deliberately mapped before design. Do not keep only the big title while dropping supporting copy.
- The design is reconstructed, not recolored. Every revised page must have a new composition, page role, and information structure when the source layout was weak.
- The deck feels bright, mature, and premium. Use brand color as a disciplined system, not as a heavy flood fill.
- Page roles are unmistakable: cover, contents, section divider, body infographic, matrix, roadmap, capability map, comparison, or appendix should each look and behave differently.
- Approved pages are locked. Regenerate only rejected or missing pages unless the user asks for a full restyle.
- Final delivery includes evidence: PPTX, image manifest, page prompts, contact sheet or rendered previews, and QA report.

## Source Copy Rules

Before image generation, create a page-level copy map.

For each source slide record:

- `source_title`: exact source title.
- `source_body_copy`: exact body copy, tables, labels, captions, and caveats.
- `must_visible`: text that must appear on the slide image or deterministic overlay.
- `can_visualize`: source text that can become callouts, tags, information cards, map labels, journey steps, or matrix cells.
- `notes_only`: long detail that should remain in speaker notes/source map.
- `must_not_invent`: logos, slogans, dates, numbers, customer names, product names, awards, certifications, and chart values that are not in the source.

Do not paraphrase or "refine" customer copy unless the user explicitly asks for rewriting. If the user says text must use the PPT wording, treat the source copy as the writing authority. You may structure it into shorter visible labels, but the wording should stay source-grounded.

If Image2 Chinese text is too risky for exact long copy, use one of these routes:

- Reduce visible text and regenerate with Image2 when exact wording is not mission-critical.
- Use deterministic text overlay only after the user has approved typographic precision over full Image2 text rendering, and record the approval in authoring artifacts.

## Design Direction

Interpret comments like "更高级", "更屌", "设计感不够", "不像 image 设计过" as a request for stronger art direction and clearer composition, not random decoration.

Good design moves:

- editorial contents cards with unique images, chapter numbers, titles, and short source-grounded hints;
- full-bleed cover hero with stable title typography and generous space;
- capability maps, information walls, process journeys, matrix cards, and annotated scene cards for dense body pages;
- magazine-like asymmetry, disciplined margins, precise hierarchy, and mixed scales;
- bright white, light gray, glass, clean green accents, and soft depth for formal technology decks;
- page-specific visual roles so adjacent pages do not reuse the same hero scene.

Avoid:

- palette-only changes that keep the old layout;
- unexplained oversized numbers, decorative codes, or giant section counts;
- fake logos or imagined brand marks;
- trendy poster chaos for formal client review;
- repeated showroom hall, sand table, dashboard wall, map screen, or thumbnail across adjacent pages;
- generic background with a title pasted on top;
- small unreadable paragraphs inside generated images.

## Page Role Grammar

Define page roles before generating a batch.

### Cover

- Use a strong hero scene, but keep title typography steady and report-like.
- Do not place a logo unless a real logo asset exists in the source or the user provides one.
- The company or project name should be the visual anchor; avoid over-clever title wording.
- A cover may be cinematic, but it should still read as a serious business/report cover.

### Contents Page

- It must clearly read as `目录`.
- Use chapter numbers, section titles, and a navigational hierarchy.
- A card-based design is encouraged: one column/card per chapter, each with a distinct thumbnail or visual cue plus text.
- Do not turn contents into a second cover, exhibition render, or generic poster.
- Do not title it with internal analysis phrases such as "五段式汇报结构".
- Do not use a huge unexplained numeral such as `05` just because there are five sections.

### Section Divider

- Use a transition composition: chapter title, short source-grounded subtitle if available, and a distinct visual treatment.
- It should bridge into the next section, not repeat cover imagery.

### Dense Body Page

- Convert body copy into information design: cards, matrices, tag rows, timeline steps, capability maps, journey maps, before/after comparisons, or annotated scenes.
- Preserve original wording where possible in visible short text.
- Put exact long paragraphs and caveats into notes/source map.

### Table or Data Page

- If values must be exact, use deterministic chart/table assets or native PPT charts as factual inserts.
- Do not ask Image2 to invent axes, precise table values, audit-grade charts, citations, or percentages.
- For high-level reading, Image2 can visualize the pattern as a matrix, scorecard, or grouped cards.

### Background Asset

- If the user asks for a reusable background with no text, remove all text, logos, and unnecessary decorative labels.
- Preserve the style system and safe empty zones for later manual text.

## Image2 Prompt Requirements

Every customer PPT image prompt should include:

- page role and intended audience;
- exact visible Chinese text or labels allowed on the page;
- the source-grounded meaning the audience should understand;
- a specific layout grammar, not just a style phrase;
- brand palette and material system;
- forbidden patterns learned from previous rejected samples;
- "large crisp Simplified Chinese text", "no English filler text", "no extra labels", "no fake logo", and "no watermark".

Prompt formula:

```text
16:9 full-slide customer presentation design.
Audience: formal client/leadership review.
Page role: [cover / 目录 / section divider / capability map / matrix / roadmap / information wall].
Visible title: "[exact source title]".
Use these exact Simplified Chinese labels only: "[label1]", "[label2]", ...
Source meaning: [what this page must make clear].
Layout grammar: [editorial cards / asymmetric hero / annotated scene / capability map / timeline / comparison matrix].
Style lock: [brand colors, brightness, typography mood, material, lighting, margins].
Forbidden: [rejected visual patterns, repeated hero image, fake logo, unexplained giant number, extra slogans].
Rules: large crisp Simplified Chinese text, all horizontal, generous margins, no English filler text, no extra labels, no fake logo, no watermark, no fake charts.
```

## Sample-First Workflow

For important customer decks, do not run the full deck blindly.

1. Intake the source deck and extract per-slide titles/body copy.
2. Decide the route: default `image_deck`, explicit editable only if the user asks for native editability.
3. Write `deck_contract.json`, `style_spec.json`, `deck_outline.json`, `page_prompts.json`, and `source_map.json`.
4. Create a 3-5 page sample covering cover, contents, one section page, and one dense body page.
5. Generate a contact sheet so the user can judge the deck as a sequence.
6. Convert user feedback into `style_spec.json` and `page_prompts.json` updates:
   - approved page -> lock image and manifest record;
   - rejected page -> add forbidden pattern and regenerate only that page;
   - style issue -> adjust style lock before continuing;
   - source-copy issue -> update copy map and prompt fields before regenerating.
7. Continue the full deck only after the sample direction is accepted.

## QA Rubric

Use this rubric before accepting a candidate slide or delivering a batch:

- Copy: source wording preserved where required; no invented client facts; no dropped body content without notes/source-map coverage.
- Page role: cover looks like cover, contents looks like `目录`, section divider looks transitional, dense body page looks like information design.
- Composition: layout changed meaningfully when the user rejected the old structure; not merely recolored.
- Brand: enterprise color is applied as a system; result is bright and premium, not heavy, muddy, or one-note.
- Text: Chinese is readable, horizontal, not garbled, and not clipped.
- Logo: no fake logo; real logo only if provided or extracted.
- Continuity: adjacent pages do not reuse the same main generated image, hero scene, or thumbnail unless intentional.
- Art direction: no unexplained giant numerals, random decorative codes, fake slogans, watermarks, or English filler.
- Delivery: image manifest, page prompts, source map, contact sheet, PPTX validation, and package integrity checks are present.

## Common Failure Corrections

| Symptom | Correction |
| --- | --- |
| User says "只变化了色调" | Stop and redesign composition. Add a new layout grammar before regenerating. |
| Contents page title becomes "五段式汇报结构" | Restore `目录`; internal analysis terms never become client-facing titles. |
| Contents page has a huge `05` | Remove it unless the number is explicitly explained by source copy. |
| P1 and P2 use the same visual | Give cover and contents different page roles and distinct thumbnails/scenes. |
| Cover feels unstable or too trendy | Use steadier title hierarchy, more whitespace, and formal report pacing. |
| Body copy disappears | Convert source sentences into visible information cards, labels, matrix cells, or notes/source-map entries. |
| Image looks like local PPT layout, not Image2 design | Let Image2 design the full page, or use an Image2 visual base plus deterministic text only when approved. |
| Fake logo appears | Remove it and add "no fake logo; no logo unless source asset exists" to the prompt and QA. |
| User approves one page but rejects another | Lock the approved page and regenerate only the rejected page. |

## Handoff Checklist

When handing this workflow to another user or colleague, include:

- source PPT path and output workspace path;
- route decision: image deck vs explicit editable PPTX;
- accepted style lock and forbidden patterns;
- locked pages and pages still needing regeneration;
- copy-preservation policy;
- contact sheet path and QA report path;
- exact commands for authoring validation, image deck build, image deck validation, and package integrity check;
- remaining risks: text editability, Image2 Chinese fidelity, missing logo assets, or pages requiring exact data rendering.
