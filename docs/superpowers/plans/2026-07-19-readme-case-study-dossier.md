# README Case-Study Dossier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the repository homepage with a research-first case-study dossier supported by two static, project-native SVG assets and an honest staged reproduction path.

**Architecture:** Keep identity and system structure in two GitHub-safe SVGs while keeping research claims, links, commands, limitations, and collaboration guidance in Markdown. The README leads with the Phase 0 research case, proves the system through a local-data boundary map, separates working artifacts from planned research, and then provides a staged technical path for reproduction.

**Tech Stack:** GitHub Flavored Markdown, static SVG 1.1, Python 3.12–3.13, DuckDB, dlt, dbt, Rill, Gradio, Hugging Face Hub, Snip visual review.

## Global Constraints

- Describe the repository as a **research prototype**, not production-ready school software.
- Preserve the substance of the current uncommitted CUDA, Apple Silicon, CPU, GGUF, LoRA, `LFED_BACKEND`, `uv sync --extra dev --extra nl-query`, `uv run python -m app`, and evaluation-command edits in `README.md`.
- Modify only `README.md` and create `assets/readme/hero.svg` and `assets/readme/system-map.svg`; the approved spec and this plan may remain uncommitted documentation.
- Do not modify `.gitignore`, application code, data, dashboards, models, research-site files, or `.superpowers/` session files.
- Do not create an animated GIF.
- Do not use SVG scripts, `foreignObject`, remote images, remote fonts, external stylesheets, or essential animation.
- Use `viewBox` width `1200`; essential diagram text is at least `20` SVG units and supporting text is at least `18`.
- Use palette: background `#FAF8F3`, foreground `#1A1A1A`, primary `#1E3A5F`, accent `#C2703A`, success `#4A7C59`, muted surface `#E9E5DA`, muted text `#53606D`.
- The California status-grid colors `#B53A3A`, `#D77732`, `#E4BD3F`, `#5F9460`, and `#376FA3` may appear only inside the status-grid motif.
- Use Georgia/serif for display, system sans for SVG body text, and system monospace for metadata.
- Include these canonical links near the top and where technically relevant:
  - `https://research.lucidotechnologyconsulting.com/overview.html`
  - `https://huggingface.co/datasets/KDDSTLC/lfed-training-data`
  - `https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64`
  - `https://huggingface.co/spaces/KDDSTLC/LFED`
- Treat the Space as a live optional demo without promising permanent availability or restarting it.
- State that the training dataset contains 25,886 synthetic NL-to-SQL pairs and is not a substitute for Aeries/CDE warehouse inputs.
- State that the repository contains a 20-prompt evaluation set; describe the 220-prompt K12-Bench as planned research.
- Do not publish an accuracy, adoption, educational-impact, or “real users” claim.
- Omit a warehouse table count. The current local development warehouse contains 100 relations across 11 schemas, while historical documents describe narrower subsets; a single count would mislead readers.
- State that model and dependency downloads require network access before local operation.
- Direct case-study collaborators to `https://github.com/flucido/local-data-stack/issues/new`.
- Do not commit, push, publish, add attribution, or open a PR; the user has not authorized those actions.

## File Map

- Create `assets/readme/hero.svg`: first-screen identity, research-prototype status, Phase 0 callout, and simplified source-to-study path.
- Create `assets/readme/system-map.svg`: local/privacy boundary, deterministic data processing, probabilistic NL-to-SQL, Rill branch, trace capture, and human review.
- Modify `README.md`: case-study dossier narrative, canonical links, research questions, staged reproduction, artifact references, limitations, participation, and technical reference.
- Reference only `docs/superpowers/specs/2026-07-19-readme-case-study-dossier-design.md`; do not modify it during implementation unless the user changes scope.

---

### Task 1: Create the Research Atlas hero

**Files:**
- Create: `assets/readme/hero.svg`

**Interfaces:**
- Consumes: approved palette, typography, Phase 0 wording, canonical artifact categories.
- Produces: `assets/readme/hero.svg`, embedded by `README.md` with full-width sizing and semantic alt text.

- [ ] **Step 1: Verify the parent and create the asset directory**

Run:

```bash
ls .
mkdir -p assets/readme
```

Expected: the repository root listing appears, then `assets/readme/` exists. Do not add or alter `.gitignore`.

- [ ] **Step 2: Create the exact initial hero SVG**

Use the file-writing tool to create `assets/readme/hero.svg` with this content:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400" viewBox="0 0 1200 400" role="img" aria-labelledby="title desc">
  <title id="title">Local Data Stack research prototype</title>
  <desc id="desc">A local-first K-12 accountability analytics research prototype connecting Aeries and CDE data to DuckDB, dashboards, natural-language SQL, evaluation, and human review.</desc>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#C2703A"/>
    </marker>
  </defs>
  <rect width="1200" height="400" rx="24" fill="#FAF8F3"/>
  <path d="M64 76H1136" stroke="#E9E5DA"/>
  <text x="64" y="55" fill="#C2703A" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700" letter-spacing="2">PHASE 0 · CASE-STUDY COLLABORATORS WANTED</text>
  <g transform="translate(64 112)">
    <text x="0" y="60" fill="#1A1A1A" font-family="Georgia, Songti SC, serif" font-size="68">Local Data</text>
    <text x="0" y="128" fill="#1E3A5F" font-family="Georgia, Songti SC, serif" font-size="68">Stack</text>
    <text x="0" y="174" fill="#53606D" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="22">A reproducible research prototype for local AI-assisted</text>
    <text x="0" y="204" fill="#53606D" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="22">K-12 accountability analytics—and the failures worth studying.</text>
    <g transform="translate(0 232)" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">
      <rect width="116" height="38" rx="9" fill="#E9E5DA"/><text x="18" y="25" fill="#1E3A5F">DUCKDB</text>
      <rect x="128" width="82" height="38" rx="9" fill="#E9E5DA"/><text x="151" y="25" fill="#1E3A5F">DBT</text>
      <rect x="222" width="84" height="38" rx="9" fill="#E9E5DA"/><text x="243" y="25" fill="#1E3A5F">RILL</text>
      <rect x="318" width="126" height="38" rx="9" fill="#E9E5DA"/><text x="335" y="25" fill="#1E3A5F">NL→SQL</text>
    </g>
  </g>
  <g transform="translate(655 102)">
    <rect width="481" height="232" rx="18" fill="#E9E5DA" stroke="#E9E5DA"/>
    <text x="28" y="40" fill="#1E3A5F" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700" letter-spacing="1">FROM SOURCE TO STUDY</text>
    <g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="20" font-weight="650" text-anchor="middle">
      <rect x="28" y="72" width="92" height="48" rx="10" fill="#FAF8F3" stroke="#53606D"/><text x="74" y="103" fill="#1A1A1A">Aeries</text>
      <rect x="28" y="138" width="92" height="48" rx="10" fill="#FAF8F3" stroke="#53606D"/><text x="74" y="169" fill="#1A1A1A">CDE</text>
      <path d="M132 129H178" stroke="#C2703A" stroke-width="2" marker-end="url(#arrow)"/>
      <rect x="190" y="105" width="104" height="48" rx="10" fill="#1E3A5F"/><text x="242" y="136" fill="#FAF8F3">DuckDB</text>
      <path d="M306 129H348" stroke="#C2703A" stroke-width="2" marker-end="url(#arrow)"/>
      <rect x="360" y="72" width="92" height="48" rx="10" fill="#FAF8F3" stroke="#53606D"/><text x="406" y="103" fill="#1A1A1A">Rill</text>
      <rect x="360" y="138" width="92" height="48" rx="10" fill="#FAF8F3" stroke="#53606D"/><text x="406" y="169" fill="#1A1A1A">NL→SQL</text>
    </g>
    <path d="M406 186V192H242V164" fill="none" stroke="#4A7C59" stroke-width="2" marker-end="url(#arrow)"/>
    <text x="242" y="220" text-anchor="middle" fill="#4A7C59" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">TRACE · REVIEW · STUDY</text>
  </g>
  <g transform="translate(1082 28)">
    <rect width="12" height="12" rx="2" fill="#B53A3A"/><rect x="16" width="12" height="12" rx="2" fill="#D77732"/><rect x="32" width="12" height="12" rx="2" fill="#E4BD3F"/>
    <rect y="16" width="12" height="12" rx="2" fill="#D77732"/><rect x="16" y="16" width="12" height="12" rx="2" fill="#5F9460"/><rect x="32" y="16" width="12" height="12" rx="2" fill="#376FA3"/>
  </g>
</svg>
```

- [ ] **Step 3: Validate the hero’s XML and GitHub-safe feature set**

Run:

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('assets/readme/hero.svg'); print('hero XML: PASS')"
python3 -c "from pathlib import Path; import re; s=Path('assets/readme/hero.svg').read_text(); stripped=re.sub(r'xmlns(?::\\w+)?=\"[^\"]*\"','',s); banned=['<script','foreignObject','@import']; found=[x for x in banned if x in stripped]; urls=re.findall(r'https?://', stripped); assert not found and not urls, (found, urls); print('hero safety: PASS')"
```

Expected:

```text
hero XML: PASS
hero safety: PASS
```

- [ ] **Step 4: Review the hero visually**

Run:

```bash
snip open assets/readme/hero.svg --message "Review the Research Atlas hero at GitHub width: title, Phase 0 status, pipeline legibility, and project-specific status-grid motif."
```

Expected: Snip returns `status: "approved"`. If it returns `changes_requested`, apply only the requested visual corrections, read the returned `path` when `edited: true`, rerun the XML/safety commands, and open the revised SVG once more.

- [ ] **Step 5: Review the task diff**

Run:

```bash
git diff -- assets/readme/hero.svg
git status --short assets/readme/hero.svg
```

Expected: only `assets/readme/hero.svg` is new for this task.

---

### Task 2: Create the local-to-evidence system map

**Files:**
- Create: `assets/readme/system-map.svg`

**Interfaces:**
- Consumes: repository flow `Aeries/CDE → dlt/dbt → DuckDB → Rill/NL-to-SQL → traces → human review` and the hero’s visual grammar.
- Produces: `assets/readme/system-map.svg`, embedded by the README and explained in adjacent Markdown.

- [ ] **Step 1: Create the exact initial system-map SVG**

Use the file-writing tool to create `assets/readme/system-map.svg` with this content:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650" role="img" aria-labelledby="title desc">
  <title id="title">Local Data Stack system map</title>
  <desc id="desc">Aeries and CDE data move through deterministic ingestion and transformation into a local DuckDB warehouse. Rill dashboards and a local natural-language SQL model produce reviewable outputs and evaluation traces for a supervised case study.</desc>
  <defs>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#1E3A5F"/></marker>
    <marker id="arrow-rust" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#C2703A"/></marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#4A7C59"/></marker>
  </defs>
  <rect width="1200" height="650" rx="24" fill="#FAF8F3"/>
  <text x="56" y="62" fill="#1A1A1A" font-family="Georgia, Songti SC, serif" font-size="42">From district records to reviewable research evidence</text>
  <text x="56" y="96" fill="#53606D" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" font-size="20">Deterministic data processing stays separate from probabilistic model output.</text>
  <rect x="252" y="126" width="690" height="444" rx="20" fill="#E9E5DA" stroke="#1E3A5F" stroke-width="2" stroke-dasharray="8 8"/>
  <text x="278" y="158" fill="#1E3A5F" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700" letter-spacing="1">LOCAL DATA + INFERENCE BOUNDARY</text>
  <g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">
    <text x="56" y="170" fill="#C2703A" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">SOURCES</text>
    <rect x="56" y="192" width="156" height="68" rx="12" fill="#FAF8F3" stroke="#53606D"/><text x="134" y="220" text-anchor="middle" fill="#1A1A1A" font-size="22" font-weight="700">Aeries SIS</text><text x="134" y="246" text-anchor="middle" fill="#53606D" font-size="18">district exports</text>
    <rect x="56" y="282" width="156" height="68" rx="12" fill="#FAF8F3" stroke="#53606D"/><text x="134" y="310" text-anchor="middle" fill="#1A1A1A" font-size="22" font-weight="700">CDE</text><text x="134" y="336" text-anchor="middle" fill="#53606D" font-size="18">public files</text>
    <path d="M212 226H292" stroke="#1E3A5F" stroke-width="2" marker-end="url(#arrow-blue)"/><path d="M212 316H292" stroke="#1E3A5F" stroke-width="2" marker-end="url(#arrow-blue)"/>
    <rect x="304" y="208" width="170" height="126" rx="14" fill="#FAF8F3" stroke="#53606D"/>
    <text x="389" y="240" text-anchor="middle" fill="#1A1A1A" font-size="22" font-weight="700">dlt + dbt</text>
    <text x="389" y="269" text-anchor="middle" fill="#53606D" font-size="18">ingest · stage</text>
    <text x="389" y="294" text-anchor="middle" fill="#53606D" font-size="18">transform · test</text>
    <text x="389" y="319" text-anchor="middle" fill="#4A7C59" font-size="18" font-weight="700">deterministic</text>
    <path d="M474 271H526" stroke="#1E3A5F" stroke-width="2" marker-end="url(#arrow-blue)"/>
    <rect x="526" y="198" width="230" height="146" rx="14" fill="#1E3A5F"/>
    <text x="641" y="236" text-anchor="middle" fill="#FAF8F3" font-size="24" font-weight="700">DuckDB</text>
    <text x="641" y="267" text-anchor="middle" fill="#E9E5DA" font-size="18">multi-schema warehouse</text>
    <text x="641" y="296" text-anchor="middle" fill="#E9E5DA" font-size="18">student_id_hash</text>
    <text x="641" y="325" text-anchor="middle" fill="#E9E5DA" font-size="18">read-only query path</text>
    <path d="M756 238H770" stroke="#1E3A5F" stroke-width="2" marker-end="url(#arrow-blue)"/>
    <path d="M756 304H770" stroke="#C2703A" stroke-width="2" marker-end="url(#arrow-rust)"/>
    <rect x="782" y="190" width="132" height="94" rx="12" fill="#FAF8F3" stroke="#53606D"/>
    <text x="848" y="225" text-anchor="middle" fill="#1A1A1A" font-size="22" font-weight="700">Rill</text>
    <text x="848" y="253" text-anchor="middle" fill="#53606D" font-size="18">4 indicators</text>
    <rect x="782" y="304" width="132" height="118" rx="12" fill="#FAF8F3" stroke="#C2703A" stroke-width="2"/>
    <text x="848" y="338" text-anchor="middle" fill="#1A1A1A" font-size="22" font-weight="700">NL→SQL</text>
    <text x="848" y="366" text-anchor="middle" fill="#53606D" font-size="18">local model</text>
    <text x="848" y="395" text-anchor="middle" fill="#C2703A" font-size="18" font-weight="700">probabilistic</text>
    <rect x="304" y="390" width="418" height="132" rx="14" fill="#FAF8F3" stroke="#4A7C59" stroke-width="2"/>
    <text x="330" y="424" fill="#4A7C59" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">RESEARCH RECORD</text>
    <text x="330" y="458" fill="#1A1A1A" font-size="20">question · generated SQL · result</text>
    <text x="330" y="489" fill="#1A1A1A" font-size="20">execution match · exact match · latency</text>
    <path d="M782 402H734V456H722" fill="none" stroke="#4A7C59" stroke-width="2" marker-end="url(#arrow-green)"/>
    <text x="976" y="170" fill="#C2703A" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">EXTERNAL INPUT</text>
    <rect x="974" y="192" width="170" height="92" rx="12" fill="#FAF8F3" stroke="#53606D"/>
    <text x="1059" y="224" text-anchor="middle" fill="#1A1A1A" font-size="20" font-weight="700">Model download</text>
    <text x="1059" y="252" text-anchor="middle" fill="#53606D" font-size="18">9–10 GB class</text>
    <path d="M974 238H932V350H914" fill="none" stroke="#C2703A" stroke-width="2" marker-end="url(#arrow-rust)"/>
    <text x="976" y="366" fill="#4A7C59" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18" font-weight="700">REVIEW</text>
    <rect x="974" y="388" width="170" height="116" rx="12" fill="#FAF8F3" stroke="#4A7C59" stroke-width="2"/>
    <text x="1059" y="422" text-anchor="middle" fill="#1A1A1A" font-size="20" font-weight="700">Human check</text>
    <text x="1059" y="451" text-anchor="middle" fill="#53606D" font-size="18">SQL · chart</text>
    <text x="1059" y="480" text-anchor="middle" fill="#53606D" font-size="18">case-study evidence</text>
    <path d="M722 480H960" stroke="#4A7C59" stroke-width="2" marker-end="url(#arrow-green)"/>
  </g>
  <g transform="translate(56 592)" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="18">
    <circle cx="8" cy="-6" r="6" fill="#1E3A5F"/><text x="24" y="0" fill="#53606D">deterministic path</text>
    <circle cx="232" cy="-6" r="6" fill="#C2703A"/><text x="248" y="0" fill="#53606D">model path</text>
    <circle cx="414" cy="-6" r="6" fill="#4A7C59"/><text x="430" y="0" fill="#53606D">evidence + review</text>
  </g>
</svg>
```

- [ ] **Step 2: Validate the system map’s XML and GitHub-safe feature set**

Run:

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('assets/readme/system-map.svg'); print('system map XML: PASS')"
python3 -c "from pathlib import Path; import re; s=Path('assets/readme/system-map.svg').read_text(); stripped=re.sub(r'xmlns(?::\\w+)?=\"[^\"]*\"','',s); banned=['<script','foreignObject','@import']; found=[x for x in banned if x in stripped]; urls=re.findall(r'https?://', stripped); assert not found and not urls, (found, urls); print('system map safety: PASS')"
```

Expected:

```text
system map XML: PASS
system map safety: PASS
```

- [ ] **Step 3: Review the system map visually**

Run:

```bash
snip open assets/readme/system-map.svg --message "Review the system map at GitHub width: local boundary, deterministic versus probabilistic paths, model download, trace capture, and human review."
```

Expected: Snip returns `status: "approved"`. If it returns `changes_requested`, apply only the requested corrections, read the returned `path` when `edited: true`, rerun XML/safety validation, and reopen the revised asset.

- [ ] **Step 4: Review the task diff**

Run:

```bash
git diff -- assets/readme/system-map.svg
git status --short assets/readme/system-map.svg
```

Expected: only `assets/readme/system-map.svg` is new for this task.

---

### Task 3: Rewrite the README as a case-study dossier

**Files:**
- Modify: `README.md:1-202`
- Reference: `docs/superpowers/specs/2026-07-19-readme-case-study-dossier-design.md:1-369`
- Reference: `pyproject.toml:5-121`
- Reference: `nl_query/model_inference.py:14-19,79`
- Reference: `nl_query/eval.py:1-91,270`
- Reference: `nl_query/eval_test_set.jsonl:1-20`
- Reference: `docs/known-issues-rill-metrics-gap.md:1-61`

**Interfaces:**
- Consumes: `assets/readme/hero.svg`, `assets/readme/system-map.svg`, repository commands, canonical research/Hugging Face URLs, and current uncommitted backend notes.
- Produces: the complete GitHub homepage and all image embeds, anchors, commands, limitations, and collaboration links.

- [ ] **Step 1: Re-read the current README and isolate its uncommitted additions**

Run:

```bash
git diff -- README.md
git status --short README.md
```

Expected: the diff includes backend selection, GGUF guidance, `LFED_BACKEND`, `uv sync --extra dev --extra nl-query`, `uv run python -m app`, and the updated eval command. Keep all of that substance in the rewrite.

- [ ] **Step 2: Replace `README.md` with this exact section order**

Use the file-writing tool. Preserve the commands and claims specified below; tighten prose only when the meaning remains identical.

````markdown
<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="Local Data Stack—a research prototype for local-first K-12 accountability analytics">
</p>

<p align="center">
  <a href="https://research.lucidotechnologyconsulting.com/overview.html">Research overview</a> ·
  <a href="https://huggingface.co/datasets/KDDSTLC/lfed-training-data">Training data</a> ·
  <a href="https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64">r=64 model</a> ·
  <a href="https://huggingface.co/spaces/KDDSTLC/LFED">Live demo</a> ·
  <a href="#reproduce-locally">Reproduce locally</a>
</p>

> [!IMPORTANT]
> **Research status:** LFED is a working research prototype in Phase 0—case-study preparation and collaborator search. The software artifacts are public; the district case study and K12-Bench study are planned. This repository is not presented as production-ready school software.

## The research case

Open K-12 analytics systems are difficult to study because district data is private, source systems are fragmented, and accountability metrics contain state-specific semantics. Local Data Stack provides an inspectable artifact for asking a narrower question: what changes when district administrators can query accountability data through an open, local-first stack—and where do the language-model components fail?

The first study is organized around three research questions:

1. **Adoption:** How do district administrators use a natural-language query layer to investigate accountability data?
2. **Failure modes:** Which accountability-semantic questions fail, and how do users detect or recover from plausible but incorrect SQL?
3. **Equity of access:** Does open-source natural-language tooling change who can ask district data questions?

Read the [60-second overview](https://research.lucidotechnologyconsulting.com/overview.html), [visual explainer](https://research.lucidotechnologyconsulting.com/explainer.html), [research synthesis](https://research.lucidotechnologyconsulting.com/synthesis.html), and [strategic pressures](https://research.lucidotechnologyconsulting.com/strategic-pressures.html).

## How the research artifact works

<p align="center">
  <img src="./assets/readme/system-map.svg" width="100%" alt="Aeries and CDE data flow through local ingestion and DuckDB into Rill, natural-language SQL, evaluation traces, and human review">
</p>

- **Sources:** Aeries SIS exports and California Department of Education public files.
- **Deterministic path:** dlt ingestion and dbt transformations build a multi-schema DuckDB warehouse.
- **Privacy boundary:** student identities use the pseudonymized `student_id_hash`; the query path is read-only and schema-aware.
- **Interfaces:** Rill provides state-accountability dashboards; the local model generates DuckDB SQL from natural-language questions.
- **Evidence:** the evaluation harness records questions, generated SQL, results, execution match, exact match, and latency when a run is executed.
- **Review:** generated SQL and charts require human review before operational use.

## Built now; studied next

### Available now

- DuckDB warehouse framework with dlt ingestion and dbt transformations.
- Four Rill views aligned to Chronic Absenteeism, Suspension, ELA, and English Learner Progress.
- [25,886-pair synthetic NL-to-SQL training dataset](https://huggingface.co/datasets/KDDSTLC/lfed-training-data).
- [Warehouse-schema r=64 LoRA adapter](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64) and a GGUF build for llama.cpp.
- [Public Gradio Space](https://huggingface.co/spaces/KDDSTLC/LFED) for trying the interface when the hosted runtime is available.
- Twenty hand-curated evaluation prompts with execution-match and exact-match scoring.

### Planned research

- A supervised 30-day district case study with usage-log analysis and semi-structured interviews.
- A case-study paper on adoption, failure modes, and equity of access.
- K12-Bench: a planned 220-prompt, multi-model accountability-metric reasoning benchmark.

## Reproduce locally

### Prerequisites

- Python 3.12 or 3.13.
- `uv` for dependency installation and command execution.
- The Rill CLI for dashboard development.
- Network access for dependencies and Hugging Face model downloads.
- Approximately 9–10 GB for the selected model artifact, plus runtime headroom.
- Aeries/CDE source data for a full district reproduction. The included five-row Parquet sample is useful for inspection, but it does not reproduce district results.

### 1. Install the framework

```bash
git clone https://github.com/flucido/local-data-stack.git
cd local-data-stack
uv sync --extra dev
cp .env.example .env
```

Configure `.env` with Aeries credentials or local source settings before running source-dependent pipelines.

### 2. Inspect the public sample

The repository includes `oss_framework/data/sample_data/synthetic_student_metrics.parquet`, a five-row anonymized sample for inspecting downstream columns. The [Hugging Face training dataset](https://huggingface.co/datasets/KDDSTLC/lfed-training-data) contains synthetic question/SQL pairs for model training; it is not a replacement for warehouse source data.

### 3. Build the DuckDB warehouse

```bash
cd oss_framework/dbt
uv run dbt deps
DBT_PROFILES_DIR=. uv run dbt parse
DBT_PROFILES_DIR=. uv run dbt build
cd ../..
```

The complete build depends on the configured Aeries/CDE inputs. Do not treat a successful clone as a reproduced district deployment.

### 4. Launch the Rill dashboards

```bash
cd rill_project
rill start
cd ..
```

### 5. Run the NL-to-SQL app

The app selects a backend automatically:

| Hardware | Backend | Model path |
| --- | --- | --- |
| CUDA GPU | transformers + PEFT | 4-bit Qwen2.5-Coder-14B base plus the r=64 LoRA adapter |
| Apple Silicon | llama.cpp + Metal | Local warehouse r=64 GGUF; public Hub fallback is older v1 |
| CPU | llama.cpp | Local warehouse r=64 GGUF; public Hub fallback is older v1 and slower |

Override selection with `LFED_BACKEND=transformers` or `LFED_BACKEND=llamacpp`.

```bash
uv sync --extra dev --extra nl-query
uv run hf download KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 --local-dir models/lora-warehouse-r64
cd nl_query
uv run python -m app
cd ..
```

The CUDA path uses `unsloth/qwen2.5-coder-14b-instruct-bnb-4bit` plus the r=64 LoRA adapter. The Apple Silicon/CPU resolver checks `LFED_GGUF_PATH`, then `models/lfed-qwen2.5-coder-14b-sql-warehouse-r64-Q4_K_M.gguf`, then falls back to `KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf`, the older v1 five-table model. Use the local warehouse-r64 GGUF when evaluating the current schema. Model download happens before inference becomes local.

> **Why two backends?** The 4-bit transformers base was chosen for Hugging Face Spaces ZeroGPU, where GPU access is CUDA/PyTorch-based. bitsandbytes 4-bit inference does not support Apple Silicon. On macOS, a merged Q4_K_M GGUF uses llama.cpp with Metal and is designed to fit within a 16 GB machine; the warehouse-r64 GGUF must be supplied locally because the public Hub GGUF is the older v1 fallback.

### 6. Run the evaluation harness

```bash
cd nl_query
uv run python eval.py --test-set eval_test_set.jsonl --adapter ../models/lora-warehouse-r64
cd ..
```

This runs the current 20-prompt set through the real model and writes `nl_query/traces_eval_test_set_<timestamp>.jsonl`. The repository does not publish an accuracy figure until a complete trace run is verified.

## Public artifacts

| Artifact | Link | Role |
| --- | --- | --- |
| Training data | [KDDSTLC/lfed-training-data](https://huggingface.co/datasets/KDDSTLC/lfed-training-data) | 25,886 synthetic NL-to-SQL pairs |
| Current adapter | [KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64) | Warehouse-schema r=64 LoRA |
| GGUF | [KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-gguf) | Older v1 five-table llama.cpp fallback; not equivalent to the r=64 adapter |
| Live interface | [KDDSTLC/LFED](https://huggingface.co/spaces/KDDSTLC/LFED) | Hosted Gradio demonstration |

The earlier r=32 adapter remains available as a rollback and comparison artifact at [KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora](https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora).

## Evaluation boundaries and known failure modes

The current harness reports execution match and exact match over 20 hand-curated questions. It does not yet represent the planned K12-Bench study.

Research-relevant failure modes include:

- **Year formats:** CDE commonly uses `2023-24`; Aeries-derived data may use `2023-2024`.
- **Suppression:** accountability rows marked `is_suppressed` must not be treated as ordinary observations.
- **Reporting categories:** natural-language group names do not always map directly to CDE category codes.
- **Plausible SQL:** a query can execute and return a credible chart while still answering the wrong question.
- **Rill semantics:** the model currently generates raw DuckDB SQL, not Metrics SQL against Rill metrics views. See [the documented gap](docs/known-issues-rill-metrics-gap.md).

## California School Dashboard coverage

| Indicator | Source pattern | Grades | Goal direction |
| --- | --- | --- | --- |
| Chronic Absenteeism | `chronicdownloadYYYY.txt` | TK–8 | Lower is better |
| Suspension Rate | `suspdownloadYYYY.txt` | TK–12 | Lower is better |
| Academic—ELA | `eladownloadYYYY.txt` | 3–8, 11 | Higher is better |
| English Learner Progress | `elpidownloadYYYY.txt` | 1–12 | Higher is better |

Each view carries CDE-provided Status, Change, and Performance Color values from the state’s 5×5 Status × Change grid. See the [2025 Dashboard Technical Guide](https://www.cde.ca.gov/ta/ac/cm/dashboardguide.asp).

## Participate in the case study

The project is looking for:

- **Research co-authors** who can shape the methodology and failure-mode analysis.
- **Reviewers or methods advisors** who can challenge the research questions and study design.
- **Supervised district partners** who can evaluate the workflow and document where it helps or fails.

[Open a case-study collaboration issue](https://github.com/flucido/local-data-stack/issues/new) and include your role, organization type, intended use, data environment, and desired level of involvement. Opening an issue does not guarantee onboarding, deployment support, authorship, or participation.

## Technical reference

<details>
<summary>Repository layout</summary>

```text
local-data-stack/
├── oss_framework/       # dlt, dbt, DuckDB, orchestration, tests
├── nl_query/            # Gradio, inference backends, SQL guard, evaluation
├── training/            # Pair generation and model-training workflows
├── rill_project/        # Metrics, dashboards, models, alerts, APIs
├── models/              # Local model instructions and ignored weights
├── research/            # Research explainer source
├── scripts/             # Root orchestration and contracts
└── docs/                # Data model, constraints, and known issues
```

</details>

<details>
<summary>Model training</summary>

The training pipeline generates NL-to-SQL pairs against the warehouse schema, validates generated SQL by execution, and trains a QLoRA adapter. See [`training/`](training/) and [`models/README.md`](models/README.md).

```bash
python training/generate_pairs.py --n 5000 --output training/pairs.jsonl
modal run --detach training/modal_generate.py
```

</details>

### Validation

```bash
uv run pytest oss_framework/tests/test_public_release_sanitization.py -q --no-cov
uv run python scripts/contracts/contract_tests.py
uv run pytest nl_query/tests/ -v
uv run ruff check oss_framework
uv run black --check oss_framework
uv run mypy oss_framework
```

## Project policies

- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## License

- Code and repository content: [MIT License](LICENSE)
````

- [ ] **Step 3: Resolve internal-link and local-file references**

Run:

```bash
python3 -c "from pathlib import Path; required=['assets/readme/hero.svg','assets/readme/system-map.svg','oss_framework/data/sample_data/synthetic_student_metrics.parquet','docs/known-issues-rill-metrics-gap.md','training','models/README.md','CONTRIBUTING.md','SECURITY.md','CODE_OF_CONDUCT.md','LICENSE']; missing=[p for p in required if not Path(p).exists()]; assert not missing, missing; print('local README targets: PASS')"
python3 -c "from pathlib import Path; s=Path('README.md').read_text(); urls=['https://research.lucidotechnologyconsulting.com/overview.html','https://huggingface.co/datasets/KDDSTLC/lfed-training-data','https://huggingface.co/KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64','https://huggingface.co/spaces/KDDSTLC/LFED','https://github.com/flucido/local-data-stack/issues/new']; missing=[u for u in urls if u not in s]; assert not missing, missing; print('canonical README links: PASS')"
```

Expected:

```text
local README targets: PASS
canonical README links: PASS
```

- [ ] **Step 4: Scan for prohibited or misleading claims**

Run:

```bash
python3 -c "from pathlib import Path; s=Path('README.md').read_text().lower(); banned=['100% local','no cloud dependencies','real users','~30 tables','30+ tables','220-prompt benchmark is']; found=[x for x in banned if x in s]; assert not found, found; print('claim scan: PASS')"
python3 -c "from pathlib import Path; s=Path('README.md').read_text(); required=['research prototype','not presented as production-ready','20-prompt','planned 220-prompt','25,886','human review','LFED_BACKEND']; missing=[x for x in required if x not in s]; assert not missing, missing; print('required claims: PASS')"
```

Expected:

```text
claim scan: PASS
required claims: PASS
```

If the exact phrase `planned 220-prompt` reads awkwardly in final prose, retain that phrase in a compact metadata line so this assertion remains literal and the current/planned distinction stays machine-checkable.

- [ ] **Step 5: Review the README diff against the preservation requirement**

Run:

```bash
git diff -- README.md
```

Expected: the old information architecture is replaced, while all current backend paths, model sizes, backend override, install command, launch command, and evaluation command remain represented.

---

### Task 4: Run automated README, SVG, lint, type-check, and test verification

**Files:**
- Verify: `README.md`
- Verify: `assets/readme/hero.svg`
- Verify: `assets/readme/system-map.svg`

**Interfaces:**
- Consumes: all deliverables from Tasks 1–3.
- Produces: command evidence that the README and assets satisfy repository and skill constraints without changing application code.

- [ ] **Step 1: Run the README audit**

Run:

```bash
python3 /Users/flucido/.config/opencode/skills/beautify-github-readme/scripts/audit_readme.py /Users/flucido/projects/local-data-stack/README.md
```

Expected: the audit completes without errors. Address only findings involving `README.md` or `assets/readme/`.

- [ ] **Step 2: Re-run SVG validation together**

Run:

```bash
python3 -c "import xml.etree.ElementTree as ET; [ET.parse(p) for p in ['assets/readme/hero.svg','assets/readme/system-map.svg']]; print('all SVG XML: PASS')"
python3 -c "from pathlib import Path; import re; files=['assets/readme/hero.svg','assets/readme/system-map.svg']; banned=['<script','foreignObject','@import']; found={};\nfor p in files:\n s=Path(p).read_text(); stripped=re.sub(r'xmlns(?::\\w+)?=\"[^\"]*\"','',s); hits=[x for x in banned if x in stripped]+re.findall(r'https?://',stripped);\n if hits: found[p]=hits\nassert not found, found; print('all SVG safety: PASS')"
```

Expected:

```text
all SVG XML: PASS
all SVG safety: PASS
```

- [ ] **Step 3: Verify the canonical Hugging Face artifacts without downloads or restarts**

Run:

```bash
hf datasets info KDDSTLC/lfed-training-data --format json
hf models info KDDSTLC/lfed-qwen2.5-coder-14b-sql-lora-warehouse-r64 --format json
hf spaces info KDDSTLC/LFED --format json
```

Expected: all three commands return public repository metadata. Do not run `hf spaces restart`, change hardware, or download model files.

- [ ] **Step 4: Run repository lint and formatting checks**

Run:

```bash
uv run ruff check oss_framework
uv run black --check oss_framework
```

Expected: both commands pass. If they fail in untouched files, record the existing failure and do not modify application code under this README-only scope.

- [ ] **Step 5: Run repository type-checking**

Run:

```bash
uv run mypy oss_framework
```

Expected: PASS. If it fails in untouched files, record the existing failure and do not widen scope.

- [ ] **Step 6: Run the lightweight tests and contracts referenced by the README**

Run:

```bash
uv run pytest oss_framework/tests/test_public_release_sanitization.py -q --no-cov
uv run python scripts/contracts/contract_tests.py
cd nl_query && uv run pytest tests/ -v
```

Expected: the public-release test, contracts, and mocked-model NL-query tests pass without a GPU. Do not run the real-model evaluation automatically.

- [ ] **Step 7: Check whitespace and final file scope**

Run:

```bash
git diff --check
git status --short
git diff -- README.md assets/readme/hero.svg assets/readme/system-map.svg docs/superpowers/specs/2026-07-19-readme-case-study-dossier-design.md docs/superpowers/plans/2026-07-19-readme-case-study-dossier.md
```

Expected: no whitespace errors; deliverable changes are limited to the README, two SVGs, approved spec, and this plan. Existing unrelated modifications remain present but unchanged.

---

### Task 5: Perform final GitHub-width visual review

**Files:**
- Verify: `README.md`
- Verify: `assets/readme/hero.svg`
- Verify: `assets/readme/system-map.svg`
- Create outside repository: `/var/folders/6j/9kz4t3_n06l1bbwb7pmdtsq80000gn/T/opencode/readme-preview.html`

**Interfaces:**
- Consumes: the final README and both SVG assets.
- Produces: desktop and narrow visual-review evidence plus any targeted asset corrections.

- [ ] **Step 1: Create a temporary GitHub-width preview outside the repository**

Use the file-writing tool to create `/var/folders/6j/9kz4t3_n06l1bbwb7pmdtsq80000gn/T/opencode/readme-preview.html` with this content:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Local Data Stack README preview</title>
  <style>
    * { box-sizing: border-box; }
    body { width: 900px; margin: 0; background: #ffffff; color: #1f2328; font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { width: 100%; padding: 32px 24px 56px; }
    img { display: block; width: 100%; height: auto; }
    nav { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px 18px; margin: 18px 0 28px; font-size: 14px; }
    nav a { color: #0969da; text-decoration: none; }
    .callout { margin: 0 0 32px; padding: 16px 18px; border-left: 4px solid #1e3a5f; background: #f6f8fa; }
    h2 { margin: 36px 0 12px; padding-bottom: 8px; border-bottom: 1px solid #d0d7de; font-size: 24px; line-height: 1.25; }
    p { margin: 0 0 16px; }
    ol { margin: 0 0 26px; padding-left: 28px; }
    li { margin: 8px 0; }
    .map { margin-top: 18px; }
  </style>
</head>
<body>
  <main>
    <img src="file:///Users/flucido/projects/local-data-stack/assets/readme/hero.svg" alt="Local Data Stack research prototype hero">
    <nav>
      <a href="#">Research overview</a><a href="#">Training data</a><a href="#">r=64 model</a><a href="#">Live demo</a><a href="#">Reproduce locally</a>
    </nav>
    <div class="callout"><strong>Research status:</strong> LFED is a working research prototype in Phase 0—case-study preparation and collaborator search. The software artifacts are public; the district case study and K12-Bench study are planned.</div>
    <h2>The research case</h2>
    <p>Local Data Stack provides an inspectable artifact for studying what changes when district administrators can query accountability data through an open, local-first stack—and where the language-model components fail.</p>
    <ol><li><strong>Adoption:</strong> How do administrators use the query layer?</li><li><strong>Failure modes:</strong> Which accountability-semantic questions fail?</li><li><strong>Equity of access:</strong> Does the tooling change who can ask district data questions?</li></ol>
    <h2>How the research artifact works</h2>
    <img class="map" src="file:///Users/flucido/projects/local-data-stack/assets/readme/system-map.svg" alt="Local data and research evidence system map">
  </main>
</body>
</html>
```

The preview must not be copied into the repository.

- [ ] **Step 2: Render the 900-pixel preview in Snip**

Run:

```bash
snip render --format html --message "Review the README at a conservative 900px GitHub content width: hierarchy, spacing, SVG legibility, and the transition from research case to system proof." < /var/folders/6j/9kz4t3_n06l1bbwb7pmdtsq80000gn/T/opencode/readme-preview.html
```

Expected: Snip returns `status: "approved"`. If `edited: true`, read the returned image path before changing source files.

- [ ] **Step 3: Create and render the narrow preview**

Change only the temporary preview body width from `900px` to `360px`, then run:

```bash
snip render --format html --message "Review the README at 360px: project name, research-prototype status, link wrapping, and whether essential system-map meaning remains available in adjacent text." < /var/folders/6j/9kz4t3_n06l1bbwb7pmdtsq80000gn/T/opencode/readme-preview.html
```

Expected: Snip returns `status: "approved"`. If required hero text is unreadable, simplify the SVG. If dense system-map details are unreadable but the adjacent Markdown carries the complete meaning, retain the map and verify the alt text remains descriptive.

- [ ] **Step 4: Re-run targeted validation after visual corrections**

Run:

```bash
python3 -c "import xml.etree.ElementTree as ET; [ET.parse(p) for p in ['assets/readme/hero.svg','assets/readme/system-map.svg']]; print('post-review SVG XML: PASS')"
python3 /Users/flucido/.config/opencode/skills/beautify-github-readme/scripts/audit_readme.py /Users/flucido/projects/local-data-stack/README.md
git diff --check
```

Expected: XML validation, README audit, and whitespace check pass.

- [ ] **Step 5: Present the final uncommitted diff**

Run:

```bash
git status --short
git diff --stat
git diff -- README.md assets/readme/hero.svg assets/readme/system-map.svg
```

Expected: the user can review the complete local result. Stop without committing, pushing, publishing, restarting the Space, adding attribution, or opening a PR.
