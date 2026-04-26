# Source Content Pipeline

Use this reference for every `source-to-deck` request. The goal is to produce a presentation argument, not a compressed copy of the source.

## Required Sequence

1. **Segment the source**
   - Split by headings, topic shifts, tables, figures, and repeated entities.
   - For mixed documents, create a section inventory before deciding slide content.

2. **Classify relevance**
   - `included_sections`: sections directly supporting the requested deck.
   - `excluded_sections`: unrelated sections that must not enter visible slides.
   - `uncertain_sections`: potentially relevant sections requiring a note or user clarification.

3. **Extract evidence**
   - Claims: statements the deck can make.
   - Key facts: entities, dates, actions, relationships, status.
   - Usable numbers: figures safe to show on slides.
   - Stakeholders: people, organizations, users, decision makers.
   - Conflicts/gaps: unverified claims, missing owners, unresolved terms, contradictions.

4. **Synthesize the deck angle**
   - Write one thesis.
   - Define the audience shift: what should change in the viewer's mind.
   - Choose slide count from narrative load.
   - Assign one job per slide.

5. **Map evidence**
   - Every visible claim must map to source evidence or be marked as inference.
   - Unsupported claims belong in caveats or are removed.

## `content_brief.json`

Write this before `deck_outline.json`.

```json
{
  "source_scope": "What source material was used and why.",
  "included_sections": ["section names or descriptions"],
  "excluded_sections": ["section names or descriptions"],
  "uncertain_sections": ["section names or descriptions"],
  "core_questions": ["questions the deck must answer"],
  "key_facts": [
    {"fact": "short fact", "source_ref": "source chunk or section", "confidence": "high|medium|low"}
  ],
  "usable_numbers": [
    {"number": "2-3天", "meaning": "集中培训周期", "source_ref": "source chunk"}
  ],
  "stakeholders": [
    {"name": "organization/person", "role": "role in the story"}
  ],
  "conflicts_or_gaps": [
    {"issue": "unverified resource reliability", "impact": "affects project decision"}
  ],
  "recommended_deck_angle": "one-sentence narrative recommendation"
}
```

## `deck_outline.json`

```json
{
  "thesis": "main claim",
  "audience_shift": "from X to Y",
  "slide_count": 9,
  "slides": [
    {
      "slide_number": 1,
      "slide_job": "cover|explain|compare|evidence|workflow|timeline|risk|decision|next_actions|closing",
      "main_message": "one slide-level claim",
      "evidence_refs": ["source_map ids"],
      "recommended_visual_form": "concept map|timeline|comparison|metric reveal|workflow|quote panel|field map",
      "speaker_notes": "details and caveats"
    }
  ]
}
```

## Mixed Document Guardrails

- Do not assume adjacent sections are related.
- Explicitly exclude unrelated topics in `content_brief.json`.
- If a document contains multiple project leads, create one deck around the user's requested lead and keep other leads out unless they directly support the requested decision.
- If source reliability is uncertain, make reliability verification part of the narrative rather than presenting the claim as settled.

## Quality Checks

- Does each slide answer a real audience question?
- Does every important claim point to evidence?
- Are raw paragraphs converted into diagrams, tables, timelines, comparisons, or notes?
- Are unrelated sections excluded from visible slides?
