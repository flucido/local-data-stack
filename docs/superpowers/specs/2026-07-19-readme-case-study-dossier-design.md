# README Case-Study Dossier Design

**Date:** 2026-07-19
**Status:** Approved for implementation planning
**Scope:** Full redesign of the repository root `README.md` plus two static SVG assets under `assets/readme/`

## 1. Purpose

Redesign the repository homepage as a case-study dossier for an active education data mining and learning analytics research program.

The README should help developers, data scientists, education researchers, and technically capable school partners understand the research question, inspect the working stack, reproduce it locally, evaluate its limitations, and propose a supervised case-study collaboration.

The repository must be described as a **research prototype**. The stack has working components, public models, dashboards, an evaluation harness, and a live demo, but it is not presented as ready for unsupervised school deployment.

## 2. Approved Positioning

```text
Audience:
Developers and data scientists evaluating or reproducing the work; education researchers and school partners considering a supervised case study.

One-sentence value:
A reproducible, local-first research prototype for studying how open-source K-12 accountability analytics, NL-to-SQL, and state-aligned dashboards change access to district data—and where those systems fail.

Primary proof:
A system map showing the real path from Aeries and CDE sources through the local warehouse to Rill, NL-to-SQL, evaluation traces, and human review.

First successful action:
Reproduce the stack locally through staged, prerequisite-aware instructions.

Visual theme:
Research Atlas—a warm editorial field guide with measured diagrams, source labels, and the California School Dashboard 5×5 status grid as the recurring project-native motif.
```

## 3. Goals

1. Make the research purpose and Phase 0 case-study context clear before technical detail.
2. Present the repository as a reproducible research artifact rather than a generic data-stack product.
3. Put real architecture, public models, dashboards, evaluation assets, and known failure modes ahead of broad claims.
4. Give developers a staged local reproduction path with hardware, data, storage, and network requirements stated before commands.
5. Invite researchers and school partners to open a GitHub issue about supervised case-study participation.
6. Preserve the existing uncommitted backend documentation covering CUDA, Apple Silicon, CPU fallback, GGUF, LoRA, and `LFED_BACKEND`.
7. Keep the README useful when images fail by retaining all required concepts, commands, constraints, and links in Markdown.

## 4. Non-Goals

1. Do not present the project as production-ready for district deployment.
2. Do not claim published accuracy, adoption, educational impact, or benchmark results without traceable evidence.
3. Do not duplicate the full research explainer, synthesis, or strategic-pressure documents.
4. Do not generate an animated GIF; the approved output is static SVG.
5. Do not add decorative section banners, badges, stock imagery, gradients, or generic AI graphics.
6. Do not move essential commands, requirements, or claims into images.
7. Do not change application code, model code, dashboards, data, or research-site content as part of this README redesign.
8. Do not create commits, push branches, publish assets, or add attribution without separate authorization.

## 5. Source-of-Truth Hierarchy

Use sources in this order when claims differ:

1. Executable repository code and configuration.
2. Current warehouse, model, dashboard, and test artifacts.
3. Current uncommitted README and code changes.
4. The public research site:
   - `https://research.lucidotechnologyconsulting.com/`
   - `https://research.lucidotechnologyconsulting.com/overview.html`
   - `https://research.lucidotechnologyconsulting.com/explainer.html`
   - `https://research.lucidotechnologyconsulting.com/synthesis.html`
   - `https://research.lucidotechnologyconsulting.com/strategic-pressures.html`
5. Canonical Hugging Face artifacts:
   - Training dataset: `https://huggingface.co/datasets/KDDSTLC/lfed-training-data`
   - Warehouse r=64 LoRA model: `https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`
   - Live LFED Space: `https://huggingface.co/spaces/KDDSTLC/LFED`
6. Historical documentation and model cards.

The README may link to the research site for depth, but it must not repeat a claim that conflicts with repository evidence. Research-site maturity language describing the system as shipped must be softened to the user-approved **research prototype** framing.

## 6. Claim Contract

### Claims allowed with repository evidence

- The stack integrates Aeries and California Department of Education data.
- DuckDB, dlt, dbt, Rill, Gradio, and a fine-tuned Qwen2.5-Coder-14B model are present.
- The canonical Hugging Face training dataset is public and contains 25,886 synthetic NL-to-SQL question/SQL pairs.
- The canonical warehouse r=64 LoRA model is public and identifies `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit` as its base model.
- Public LoRA and GGUF model artifacts exist.
- The public LFED Gradio Space exists and was confirmed running during design review; the README should link it without promising permanent availability.
- Four California School Dashboard indicator dashboards exist: Chronic Absenteeism, Suspension, ELA, and ELPI.
- The repository contains a 20-prompt evaluation test set and an execution/exact-match trace harness.
- CUDA/transformers and llama.cpp/GGUF backends exist with automatic selection and an `LFED_BACKEND` override.
- Student identifiers are pseudonymized through hashing where the implementation proves it.

### Claims that require verification or omission

- The exact warehouse table count. Existing documents conflict between approximately 30 tables and 19 tables.
- Any accuracy, benchmark, latency, usage, adoption, or educational-impact number.
- The statement that the system has real users.
- The statement that the complete system is 100% offline. Model download and dependency acquisition require network access before local operation.
- Any assertion that the planned 220-prompt K12-Bench already exists. The current repository evidence is a 20-prompt development/evaluation set.
- The research-site claim that no accepted EDM 2026 paper uses a real, open K-12-scale dataset unless the README attributes and links to the research synthesis rather than presenting it as independently verified repository fact.

### Required wording distinctions

- **Working today:** repository framework, local warehouse path, dashboards, model artifacts, live demo, and 20-prompt evaluation harness.
- **Research phase:** Phase 0 collaborator search and case-study preparation.
- **Planned:** 30-day case study, interviews, academic papers, and 220-prompt K12-Bench.
- **Deployment status:** research prototype suitable for technical reproduction and supervised study, not unsupervised production use in schools.

## 7. README Information Architecture

### 7.1 Hero

Use `assets/readme/hero.svg` as an integrated title and research-context module.

The hero contains:

- Category: local-first K-12 accountability analytics.
- Name: Local Data Stack.
- Concrete description: reproducible research prototype for local AI-assisted education analytics.
- Status label: Phase 0—case-study collaborators wanted.
- Project-native material: a simplified status grid and a short source-to-study path.
- Minimal metadata: DuckDB, dbt, Rill, NL-to-SQL, open source.

Immediately below the hero, Markdown provides five clear links:

- Research overview: `https://research.lucidotechnologyconsulting.com/overview.html`.
- Training data: `https://huggingface.co/datasets/KDDSTLC/lfed-training-data`.
- Warehouse r=64 model: `https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`.
- Live demo: `https://huggingface.co/spaces/KDDSTLC/LFED`.
- Local reproduction section in the README.

### 7.2 Research Case

Explain the gap, current study status, and why the repository exists. Keep it concise and link to the research site for the full synthesis.

Present the three active research questions:

1. Adoption: how district administrators use the stack.
2. Failure modes: where accountability-semantic NL-to-SQL fails and how users detect or recover.
3. Equity of access: whether open-source natural-language tooling changes who can ask district data questions.

Clearly label these as research questions, not validated outcomes.

### 7.3 System Map

Embed `assets/readme/system-map.svg`, followed by a compact Markdown explanation.

Approved flow:

```text
Aeries SIS + CDE public data
  → dlt ingestion + dbt transformation
  → local DuckDB warehouse and privacy boundary
  → Rill dashboards
  → NL-to-SQL model
  → SQL/result/latency traces
  → human review and case-study evidence
```

The visual must distinguish:

- Local data and inference boundary.
- External downloads required before local use.
- Deterministic transformations from probabilistic model output.
- Human review after model-generated SQL.

### 7.4 What Exists vs. What Is Planned

Use two concise Markdown lists rather than a dense comparison graphic.

**Exists now:**

- Local warehouse framework and data layers.
- Four Rill indicator dashboards.
- Public 25,886-pair synthetic NL-to-SQL training dataset.
- Public warehouse r=64 LoRA and GGUF model artifacts.
- Gradio NL-to-SQL interface and hosted LFED Space.
- 20-prompt evaluation set and trace harness.

**Planned research:**

- Supervised district case study.
- 30-day usage analysis and interviews.
- Case-study paper.
- 220-prompt K12-Bench and multi-model study.

### 7.5 Reproduce Locally

The reproduction path is the primary action and must be staged so readers can stop before expensive or data-dependent steps.

1. **Prerequisites:** operating system, Python version, `uv`, DuckDB/dbt/Rill requirements, available storage, network access, and expected model size.
2. **Install and inspect:** clone, environment setup, dependency installation, and commands that do not require a model.
3. **Build or connect data:** explain required Aeries/CDE inputs, synthetic/sample-data availability, and privacy expectations before running warehouse transforms. Link the public Hugging Face training dataset separately and state that its synthetic NL-to-SQL pairs are model-training material, not a substitute for the warehouse inputs.
4. **Run dashboards:** start Rill after the warehouse is available.
5. **Run NL-to-SQL:** explain backend auto-selection, CUDA transformers, Apple Silicon/CPU llama.cpp, model download, GGUF size, and override behavior.
6. **Run evaluation:** distinguish lightweight tests from a real-model evaluation run and show where traces are written.

Do not imply that cloning alone reproduces district results. Required source data and any unavailable fixtures must be explicit.

### 7.6 Evaluation and Known Failure Modes

Explain the evidence currently available:

- 20 hand-curated prompts.
- Execution match and exact match.
- JSONL traces containing result and runtime fields when generated.

Do not publish an accuracy number while the tracked trace artifact is empty or otherwise unverified.

Surface research-relevant failure modes:

- CDE and Aeries year-format mismatch.
- Suppression handling.
- Reporting-category code ambiguity.
- Plausible but incorrect model-generated SQL.
- Rill metrics SQL versus raw DuckDB SQL gap.

State that model-generated SQL and charts require human review before operational use.

### 7.7 Case-Study Participation

Include three collaborator roles in compressed form:

- Research co-author.
- Reviewer or methods advisor.
- Supervised district case-study partner.

The primary call to action opens a GitHub issue. It should ask the reader to identify their role, organization type, intended use, data environment, and desired level of involvement. Do not imply guaranteed onboarding, deployment support, authorship, or research participation.

### 7.8 Technical Reference

Move lower-level detail below the narrative and reproduction path:

- Repository layout.
- Model/backend matrix.
- Dashboard coverage.
- Training notes.
- Validation commands.
- Known constraints.
- Contribution, security, license, and code-of-conduct links.

Use collapsible `<details>` blocks only where they reduce scanning cost without hiding critical requirements.

## 8. Visual System

### 8.1 Palette

| Role | Value |
| --- | --- |
| Background | `#FAF8F3` |
| Foreground | `#1A1A1A` |
| Primary | `#1E3A5F` |
| Accent | `#C2703A` |
| Success | `#4A7C59` |
| Muted surface | `#E9E5DA` |
| Muted text | `#53606D` |

The five California status colors may appear only inside the status-grid motif. They should not become the general README palette.

### 8.2 Typography

- Display: `Georgia`, `Songti SC`, `serif`.
- Body inside SVG: `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`.
- Metadata: `ui-monospace`, `SFMono-Regular`, `Menlo`, `monospace`.
- Markdown remains GitHub-native.

### 8.3 Shape and Spacing

- Full-width SVG viewBox: 1200 units.
- Hero height: approximately 380–420 units.
- System map height: approximately 520–680 units.
- Edge safety: 56–64 units.
- Primary radius: 20–24 units for outer frames; 8–12 units for internal modules.
- Stroke: 1–2 units.
- Spacing rhythm: multiples of 8 units.
- No heavy shadow; use thin rules, restrained fills, and whitespace.

### 8.4 Motif

Use the California School Dashboard 5×5 Status × Change grid as a small recurring marker in the hero and system map. It communicates project-specific accountability semantics and should not be used as decorative wallpaper.

### 8.5 Composition

- **Hero:** integrated editorial composition with the title and simplified research pipeline sharing one grid.
- **System map:** annotated specimen showing sources, privacy boundary, deterministic processing, probabilistic query generation, traces, and human review.
- **Density:** sparse editorial at the top, compact technical in the system map, plain Markdown for the rest.

## 9. Asset Requirements

### `assets/readme/hero.svg`

- Static, GitHub-safe SVG.
- `viewBox="0 0 1200 400"` or nearby approved height.
- Complete background for GitHub light and dark surroundings.
- `<title>` and `<desc>`.
- No scripts, `foreignObject`, remote fonts, remote images, or essential animation.
- Required type remains legible at a 900 CSS-pixel desktop width.
- At 360 CSS pixels, the project name and one-sentence purpose remain legible; supporting details may be repeated in adjacent Markdown.

### `assets/readme/system-map.svg`

- Static, GitHub-safe SVG.
- `viewBox` width of 1200 units.
- Essential labels at least 20 SVG units; supporting labels at least 18.
- Clearly marked local/privacy boundary.
- Explicit model-download input and human-review output.
- Full explanation repeated in adjacent Markdown for mobile and accessibility.

## 10. Existing Work Preservation

`README.md` is already modified. The redesign must preserve the substance of these uncommitted additions:

- CUDA transformers backend and 4-bit base model.
- Apple Silicon/CPU llama.cpp backend and GGUF model.
- Automatic backend selection.
- `LFED_BACKEND=transformers|llamacpp` override.
- Model size and memory guidance.
- `uv sync --extra nl-query` and `uv run python -m app` workflow.
- Updated evaluation command and trace description.

These details may move or be condensed, but must not be silently deleted.

No other modified or untracked repository files are in scope.

## 11. Verification Strategy

### Content verification

- Check every quantitative claim against code, configuration, data, or a cited research source.
- Resolve or omit the conflicting table count.
- Verify all repository, research-site, Hugging Face, and issue links.
- Confirm current versus planned research artifacts are visibly separated.
- Confirm the maturity statement says research prototype.
- Confirm the case-study invitation uses GitHub issues.

### SVG verification

- Validate XML parsing.
- Check for prohibited SVG features and external resources.
- Render both assets at GitHub content width.
- Inspect at approximately 900-pixel desktop and 360-pixel mobile widths.
- Check clipping, contrast, type legibility, and dark/light page surroundings.
- Use Snip for visual review after running `snip --help` once in the session.

### README verification

Run the bundled skill audit against the root README:

```bash
python3 /Users/flucido/.config/opencode/skills/beautify-github-readme/scripts/audit_readme.py /Users/flucido/projects/local-data-stack/README.md
```

Run the repository’s documented lint, type-check, and test commands that are relevant to README claims. Expensive real-model evaluation requiring a 9–10 GB model or CUDA is not run automatically; document it as an optional manual verification unless separately authorized and available.

Review the final diff to ensure only the approved README, SVG assets, and explicitly authorized planning documents changed.

## 12. Acceptance Criteria

1. A first-time technical visitor can identify the research problem, maturity, active phase, and next action without scrolling past the first two modules.
2. The first proof is the real local system map, not decoration or an unsupported metric.
3. The README reads as a case-study dossier rather than a product landing page or generic stack catalog.
4. Developers can understand prerequisites and reproduce the system in honest stages.
5. Current and planned artifacts are not conflated.
6. Model, privacy, and evaluation limitations are visible before operational claims.
7. Existing backend documentation remains represented.
8. Both SVGs are readable, accessible, static, and GitHub-safe.
9. The research site supplies depth while the README remains the technical and reproducibility gateway.
10. The final README is clearer and more evidence-led than the current 202-line version, without decorative sprawl.
11. Unrelated modified and untracked files remain untouched.
12. The canonical Hugging Face training dataset, warehouse r=64 model, and live LFED Space are linked near the top and again where technically relevant.
13. No commit, push, publication, attribution, or external PR occurs without explicit authorization.
