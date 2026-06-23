"""
app.py — Local First Education Data Framework (LFED).

Thin Gradio controller. All logic lives in:
  - prompts.py         (system prompt, schema docs, few-shot examples)
  - model_inference.py (transformers + LoRA wrapper, SQL generation + streaming)
  - data_engine.py     (read-only warehouse attach, schema introspection, execution guard)
  - ui_strings.py      (user-facing copy: domains, errors, rephrasings)

Adapted for local-data-stack: instead of seeding an in-memory DuckDB from
Parquet, this queries the unified warehouse (data/warehouse.duckdb) read-only
and injects its live schema into the prompt.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field

import gradio as gr

# spaces.GPU is only available on HF Spaces — use a no-op locally
try:
    import spaces

    _gpu_decorator = spaces.GPU(duration=30)
except ImportError:
    _gpu_decorator = lambda fn: fn  # no-op for local dev

from data_engine import QueryTimeoutError, create_session, execute_safe, get_schema_info
from model_inference import generate_sql_streaming, load_model
from ui_strings import (
    ABOUT_MODAL_FAQ,
    ABOUT_MODAL_HINT,
    ABOUT_MODAL_HOW_IT_WORKS,
    ABOUT_MODAL_INTRO,
    ABOUT_MODAL_PRIVACY,
    ABOUT_MODAL_TITLE,
    ABOUT_MODAL_WHAT_IT_IS_BULLETS,
    ABOUT_MODAL_WHAT_IT_ISNT_BULLETS,
    APP_TAGLINE,
    APP_TITLE,
    DOMAIN_SECTIONS,
    ERROR_REPHRASINGS,
    FIRST_VISIT_NUDGE,
    HOW_IT_WORKS,
    INPUT_PROMPT_EMPTY,
    PREVIOUS_RIBBON_TEMPLATE,
    PRIVACY_EXPLAINER,
    SQL_DISCLOSURE_LABEL,
    SUMMARY_TEMPLATES,
    WHAT_THIS_IS_NOT_ONE_LINER,
    WHAT_THIS_IS_ONE_LINER,
)

# ── Startup ───────────────────────────────────────────────────────────

print("🚀 Starting Local First Education Data Framework...")

# Model is loaded lazily (it's a 14B model). Importing this module must not
# require a GPU — generate_sql_streaming() will load on first use, or we load
# it explicitly in __main__ before launching the UI.
llm = None

# Live warehouse schema, introspected once and reused for every prompt.
_schema_cache: dict | None = None
_schema_lock = threading.Lock()


def get_warehouse_schema() -> dict:
    """Introspect (and cache) the warehouse schema for prompt injection."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    with _schema_lock:
        if _schema_cache is None:
            conn = create_session()
            try:
                _schema_cache = get_schema_info(conn)
            finally:
                conn.close()
    return _schema_cache


# ── Result + session state ────────────────────────────────────────────


@dataclass
class PriorAnswer:
    """One-step memory: the most recent successful answer, kept so the next
    question can refer to it without the user having to remember."""

    question: str
    summary: str
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)
    row_count: int = 0


def empty_prior() -> dict | None:
    return None


def format_result_df(df):
    """Round floats to 2 decimal places. If a column name suggests a
    percentage (contains 'percent', '%', or ends with '_pct' / '_rate' /
    '_ratio'), format values as a percentage with 2dp + '%' suffix.

    Rate/ratio columns may already be returned as percentages (e.g. 10.0)
    or as 0-1 proportions (e.g. 0.10). We scale only when the value is
    clearly a proportion (0 <= value <= 1). Values outside that range are
    treated as already-scaled percentages.

    Preserves integer dtype for integer columns."""
    if df is None:
        return None
    import pandas as pd

    df = df.copy()
    for col in df.columns:
        col_lower = str(col).lower()
        is_pct = (
            "percent" in col_lower
            or "%" in col_lower
            or col_lower.endswith("_pct")
            or col_lower.endswith("_rate")
            or col_lower.endswith("_ratio")
        )
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if is_pct:

            def _fmt(v):
                if pd.isna(v):
                    return v
                val = float(v)
                # Scale only if the value looks like a 0-1 proportion.
                if 0 <= val <= 1:
                    val *= 100
                return f"{round(val, 2):.2f}%"

            df[col] = df[col].apply(_fmt)
        elif pd.api.types.is_integer_dtype(df[col]):
            pass  # keep integers as integers
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].apply(lambda v: round(float(v), 2) if pd.notna(v) else v)
    return df


def build_summary(question: str, df, row_count: int) -> str:
    """One-sentence plain-English summary of a result.

    Best-effort heuristic — falls back to a neutral 'N rows returned' line
    when the shape doesn't match any pattern.
    """
    if df is None or row_count == 0:
        return "I didn't find anything that matches that question."
    cols = list(df.columns)
    if row_count == 1 and len(cols) == 1:
        val = df.iloc[0, 0]
        return SUMMARY_TEMPLATES["single_value"].format(value=val)
    if row_count == 1 and len(cols) == 2:
        label = df.iloc[0, 0]
        val = df.iloc[0, 1]
        return SUMMARY_TEMPLATES["single_pair"].format(label=label, value=val)
    if len(cols) == 2 and ("school_id" in cols or "school_name" in cols):
        return SUMMARY_TEMPLATES["by_school"].format(n=row_count)
    return SUMMARY_TEMPLATES["generic"].format(n=row_count)


def rephrase_error(raw_error: str, raw_sql: str) -> str:
    """Map a model/validation/timeout error to a plain-English message that
    suggests a starter question. Always ends with 'Try:' + suggestion."""
    raw = (raw_error or "").lower()
    for marker, template in ERROR_REPHRASINGS.items():
        if marker in raw:
            suggestion = DOMAIN_SECTIONS[0]["questions"][0]
            return f"{template}\n\n**Try:** _{suggestion}_"
    suggestion = DOMAIN_SECTIONS[0]["questions"][0]
    return f"Something didn't work. Try rephrasing — for example: _{suggestion}_"


# ── Query handler ─────────────────────────────────────────────────────


@_gpu_decorator
def handle_query(user_question: str, prior_state: dict | None):
    """
    Process an admin's question end-to-end, streaming SQL as it generates.
    Updates prior_state with the new answer (for the ribbon on the next ask).
    """
    prior = _state_to_prior(prior_state)

    if not user_question or not user_question.strip():
        yield prior, "", None, "🤖", INPUT_PROMPT_EMPTY, prior_state
        return

    schema = get_warehouse_schema()

    raw_output = ""
    try:
        yield prior, "", None, "🤖", "Finding your answer…", prior_state
        for accumulated in generate_sql_streaming(
            user_question, llm=llm, max_tokens=192, schema=schema
        ):
            raw_output = accumulated
            yield prior, raw_output, None, "🤖", "Finding your answer…", prior_state
    except Exception as e:
        yield prior, raw_output, None, "❌", rephrase_error(str(e), ""), prior_state
        return

    try:
        yield prior, raw_output, None, "🦆", "Looking it up…", prior_state
        conn = create_session()
        clean_sql, df = execute_safe(conn, raw_output, timeout_sec=30)
        conn.close()
        row_count = len(df)
        df = format_result_df(df)
        summary = build_summary(user_question, df, row_count)

        new_prior = PriorAnswer(
            question=user_question,
            summary=summary,
            sql=clean_sql,
            columns=list(df.columns),
            rows=df.values.tolist(),
            row_count=row_count,
        )
        new_state = _prior_to_state(new_prior)
        yield new_prior, clean_sql, df, "✅", summary, new_state
    except ValueError as e:
        yield prior, raw_output, None, "⚠️", rephrase_error(str(e), raw_output), prior_state
    except QueryTimeoutError as e:
        yield prior, raw_output, None, "⏱️", rephrase_error(str(e), raw_output), prior_state
    except Exception as e:
        yield prior, raw_output, None, "❌", rephrase_error(str(e), raw_output), prior_state


def _prior_to_state(p: PriorAnswer | None) -> dict | None:
    if p is None:
        return None
    return {
        "question": p.question,
        "summary": p.summary,
        "sql": p.sql,
        "columns": p.columns,
        "rows": p.rows,
        "row_count": p.row_count,
    }


def _state_to_prior(s: dict | None) -> PriorAnswer | None:
    if s is None:
        return None
    return PriorAnswer(
        question=s.get("question", ""),
        summary=s.get("summary", ""),
        sql=s.get("sql", ""),
        columns=s.get("columns", []),
        rows=s.get("rows", []),
        row_count=s.get("row_count", 0),
    )


def bring_back_prior(prior_state: dict | None) -> tuple:
    """When the user clicks 'bring back' on the previous-answer ribbon,
    re-render the previous answer in the result panels and hide the
    bring-back button (since the prior is now the active result)."""
    prior = _state_to_prior(prior_state)
    if prior is None:
        return (
            "",  # ribbon text (empty)
            None,  # sql
            None,  # df
            "",  # summary html
            prior_state,
            gr.update(visible=False),  # bring-back button
        )
    # prior.rows are stored as list[list]; rebuild the formatted display
    import pandas as pd

    df = pd.DataFrame(prior.rows, columns=prior.columns) if prior.columns else None
    df = format_result_df(df)
    return (
        "",  # clear ribbon text
        prior.sql,
        df,
        f'<p class="result-summary">{prior.summary}</p>',
        prior_state,
        gr.update(visible=False),  # hide the bring-back button
    )


# ── UI Theme & Styles ──────────────────────────────────────────────────

catalyst_theme = gr.themes.Base(
    primary_hue="zinc",
    neutral_hue="zinc",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"],
).set(
    body_background_fill="#F3F4F6",
    body_text_color="#111827",
    background_fill_primary="#FFFFFF",
    background_fill_secondary="#F9FAFB",
    input_background_fill="#FFFFFF",
    input_border_color="rgba(17, 24, 39, 0.10)",
    input_border_color_focus="#111827",
    button_primary_background_fill="#111827",
    button_primary_text_color="#FFFFFF",
    border_color_primary="rgba(17, 24, 39, 0.10)",
    block_border_width="0px",
)


CUSTOM_CSS = """\\
/* ── Layout ────────────────────────────────────────────────────────── */
body, #root, .gradio-container, .gradio-container > .main, .gradio-container .app {
    max-width: 960px !important;
    width: 100% !important;
    margin-left: auto !important;
    margin-right: auto !important;
    box-sizing: border-box !important;
}
.gradio-container {
    max-width: 960px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 0 1.5rem !important;
    font-size: 14px !important;
    box-sizing: border-box !important;
}
@media (max-width: 720px) {
    .gradio-container { padding: 0 1rem !important; }
}

/* ── Force light mode (kill Gradio auto-dark) ──────────────────────── */
html, html.dark, html[data-theme="dark"], .dark, .gradio-container {
    color-scheme: light !important;
}
html.dark body, .dark body, html.dark .gradio-container, .dark .gradio-container {
    background: #F3F4F6 !important;
    color: #111827 !important;
}

/* ── Header ────────────────────────────────────────────────────────── */
.app-header-wrap { padding: 1.5rem 0 0.5rem 0; }
.app-header h1 {
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0 0 0.25rem 0;
    letter-spacing: -0.01em;
}
.app-header .tagline {
    color: #6B7280;
    margin: 0;
    line-height: 1.5;
    max-width: 60ch;
}

/* ── Primary CTA ────────────────────────── */
.primary-cta {
    font-weight: 600 !important;
    padding: 8px 16px !important;
    border-radius: 0.5rem !important;
    margin-top: 0.75rem !important;
}

/* ── Domain cards ──────────────── */
.domain-row {
    display: flex !important;
    flex-direction: row !important;
    margin-top: 1.25rem !important;
    gap: 1rem !important;
    align-items: stretch !important;
}
.domain-col {
    background: #FFFFFF !important;
    border: 1px solid rgba(17, 24, 39, 0.05) !important;
    border-radius: 0.5rem !important;
    padding: 0.875rem 1rem 0.75rem 1rem !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 0.5rem !important;
    height: 100% !important;
    min-height: 7.5rem !important;
}
.domain-col-title {
    font-weight: 500 !important;
    margin: 0 0 0.25rem 0 !important;
    line-height: 1.4 !important;
    min-height: 2.8rem !important;
}
.domain-dropdown label { display: none !important; }

/* ── Result region ─────────────────────────────────────────────────── */
.result-summary {
    font-weight: 600;
    padding: 1rem 0 0.5rem 0;
    margin: 0;
    border-top: 1px solid rgba(17, 24, 39, 0.05);
}

/* ── Footer ────────────────────────────────────────────────────────── */
.app-footer {
    margin-top: 2.5rem;
    padding: 1rem 0 1.25rem 0;
    border-top: 1px solid rgba(17, 24, 39, 0.05);
    color: #6B7280;
    line-height: 1.6;
}
.app-footer h4 { font-weight: 600; margin: 0 0 0.25rem 0; }
.app-footer .footer-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
}
@media (max-width: 720px) {
    .app-footer .footer-cols { grid-template-columns: 1fr; gap: 1.25rem; }
}

/* ── About modal ───────────────────────────────────────────────────── */
#about-modal {
    position: fixed;
    inset: 0;
    background: rgba(17, 24, 39, 0.45);
    z-index: 9999;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 1rem;
}
#about-modal.visible { display: flex !important; }
.about-modal-card {
    background: #FFFFFF;
    border-radius: 0.75rem;
    max-width: 640px;
    width: 100%;
    max-height: 85vh;
    overflow-y: auto;
    padding: 1.5rem;
    color: #111827;
}
.about-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}
.about-modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: #6B7280;
}
"""

HEAD_HTML = """
<script>
function openAboutModal() {
    const modal = document.getElementById('about-modal');
    if (modal) {
        modal.classList.add('visible');
        document.body.style.overflow = 'hidden';
    }
}
function closeAboutModal() {
    const modal = document.getElementById('about-modal');
    if (modal) {
        modal.classList.remove('visible');
        document.body.style.overflow = '';
    }
}
document.addEventListener('click', function (e) {
    const modal = document.getElementById('about-modal');
    if (modal && modal.classList.contains('visible') && e.target === modal) {
        closeAboutModal();
    }
});
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAboutModal();
});
</script>
"""

# ── Component builders ────────────────────────────────────────────────


def build_explainer_html() -> str:
    return (
        f'<div class="explainer">'
        f"<h3>How this works</h3>"
        f"<p>{HOW_IT_WORKS}</p>"
        f'<h3 style="margin-top:1.5rem;">Your privacy</h3>'
        f"<p>{PRIVACY_EXPLAINER}</p>"
        f"</div>"
    )


def build_footer_html() -> str:
    return (
        f'<div class="app-footer">'
        f'<div class="footer-cols">'
        f"<div><h4>What this is</h4>"
        f"<p>{WHAT_THIS_IS_ONE_LINER}</p></div>"
        f"<div><h4>What this isn’t</h4>"
        f"<p>{WHAT_THIS_IS_NOT_ONE_LINER}</p></div>"
        f"</div>"
        f"</div>"
    )


def build_about_modal_html() -> str:
    what_is_items = "\n".join(f"<li>{item}</li>" for item in ABOUT_MODAL_WHAT_IT_IS_BULLETS)
    what_isnt_items = "\n".join(f"<li>{item}</li>" for item in ABOUT_MODAL_WHAT_IT_ISNT_BULLETS)
    faq_items = "\n".join(
        f'<details><summary>{item["q"]}</summary><p>{item["a"]}</p></details>'
        for item in ABOUT_MODAL_FAQ
    )
    return (
        f'<div id="about-modal" role="dialog" aria-modal="true" aria-labelledby="about-modal-title">'
        f'<div class="about-modal-card">'
        f'<div class="about-modal-header">'
        f'<h2 id="about-modal-title">{ABOUT_MODAL_TITLE}</h2>'
        f'<button class="about-modal-close" onclick="closeAboutModal()" aria-label="Close">×</button>'
        f"</div>"
        f"<p>{ABOUT_MODAL_INTRO}</p>"
        f"<h3>How it works</h3>"
        f"<p>{ABOUT_MODAL_HOW_IT_WORKS}</p>"
        f"<h3>What you can do</h3>"
        f"<ul>{what_is_items}</ul>"
        f"<h3>What it isn’t</h3>"
        f"<ul>{what_isnt_items}</ul>"
        f"<h3>FAQ</h3>"
        f"{faq_items}"
        f"<h3>Privacy</h3>"
        f"<p>{ABOUT_MODAL_PRIVACY}</p>"
        f'<div class="about-modal-hint">{ABOUT_MODAL_HINT}</div>'
        f"</div>"
        f"</div>"
    )


def build_demo() -> gr.Blocks:
    """Construct the Gradio app. Wrapped in a function so importing this
    module (e.g. for tests) does not build the UI or require a model."""
    with gr.Blocks(
        title="Local First Education Data Framework",
        theme=catalyst_theme,
        css=CUSTOM_CSS,
    ) as demo:
        prior_state = gr.State(value=None)
        has_asked = gr.State(value=False)

        gr.HTML(build_about_modal_html())

        with gr.Column(elem_classes="app-header-wrap"):
            gr.HTML(
                f"""
                <div class="app-header">
                    <h1>{APP_TITLE}</h1>
                    <p class="tagline">{APP_TAGLINE}</p>
                </div>
                """
            )

        with gr.Column(elem_classes="ask-block"):
            user_input = gr.Textbox(
                label="Your question",
                placeholder="Ask in plain English…",
                lines=2,
            )
            submit_btn = gr.Button(
                "Get answer",
                elem_classes="primary-cta",
                variant="primary",
            )

        starter_buttons: list[tuple[gr.components.Component, str]] = []
        with gr.Row(elem_classes="domain-row"):
            for section in DOMAIN_SECTIONS:
                with gr.Column(elem_classes="domain-col", scale=1):
                    gr.HTML(f'<div class="domain-col-title">{section["title"]}</div>')
                    dropdown = gr.Dropdown(
                        choices=section["questions"],
                        value=None,
                        label=None,
                        show_label=False,
                        elem_classes="domain-dropdown",
                    )
                    starter_buttons.append((dropdown, section["questions"]))

        first_visit = gr.HTML(
            f'<div class="first-visit-nudge">{FIRST_VISIT_NUDGE}</div>',
            visible=True,
        )

        with gr.Row(elem_classes="previous-ribbon-row"):
            previous_ribbon = gr.Markdown("", elem_classes="previous-ribbon-text")
            bring_back_btn = gr.Button(
                "Bring it back",
                elem_classes="link-button",
                size="sm",
                visible=False,
            )
        result_summary = gr.HTML(visible=False)
        data_output = gr.Dataframe(visible=False, wrap=True)
        download_output = gr.File(
            label="Download results as CSV",
            visible=False,
            elem_classes="download-csv",
            interactive=False,
        )
        sql_output = gr.Code(visible=False, language="sql", label=SQL_DISCLOSURE_LABEL)
        status = gr.Markdown("", elem_classes="status-line")

        gr.HTML(build_footer_html())
        footer_help_btn = gr.Button(
            "Read the full explainer",
            elem_classes="link-button footer-help",
            size="sm",
        )

        with gr.Group(elem_classes="explainer-wrap"):
            explainer_content = gr.HTML(value="", elem_classes="explainer-content")
            explainer_close_btn = gr.Button(
                "Close",
                elem_classes="link-button explainer-close",
                size="sm",
                visible=False,
            )

        # ── Wiring ──────────────────────────────────────────────────

        def fill_input(q: str) -> str:
            return q or ""

        def clear_dropdowns():
            return tuple(gr.update(value=None) for _ in starter_buttons)

        def on_submit(question, prior, first_time):
            has_asked_val = True
            if not question or not question.strip():
                yield (
                    "",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    None,
                    gr.update(visible=False),
                    INPUT_PROMPT_EMPTY,
                    gr.update(visible=not first_time),
                    prior,
                    has_asked_val,
                    gr.update(visible=False),
                    *clear_dropdowns(),
                )
                return
            for prior_obj, sql_text, df, emoji, status_text, new_state in handle_query(
                question, prior
            ):
                ribbon_text = (
                    PREVIOUS_RIBBON_TEMPLATE.format(summary=prior_obj.summary)
                    if prior_obj is not None
                    else ""
                )
                summary_visible = bool(status_text and emoji in ("✅",))
                has_data = df is not None

                csv_path = None
                if has_data:
                    import datetime as _dt
                    import tempfile

                    csv_path = os.path.join(
                        tempfile.gettempdir(),
                        f"lfed_result_{_dt.datetime.now(_dt.UTC).strftime('%Y%m%d_%H%M%S')}.csv",
                    )
                    df.to_csv(csv_path, index=False)

                yield (
                    ribbon_text,
                    gr.update(
                        value=(
                            f'<p class="result-summary">{status_text}</p>'
                            if summary_visible
                            else ""
                        ),
                        visible=summary_visible,
                    ),
                    gr.update(value=df, visible=has_data),
                    gr.update(value=csv_path, visible=has_data),
                    gr.update(value=sql_text, visible=bool(sql_text)),
                    f"{emoji} {status_text}",
                    gr.update(visible=False),
                    new_state,
                    has_asked_val,
                    gr.update(visible=False),
                    *clear_dropdowns(),
                )

        for dropdown, _questions in starter_buttons:
            dropdown.change(fn=fill_input, inputs=[dropdown], outputs=user_input)

        footer_help_btn.click(
            fn=lambda: (build_explainer_html(), gr.update(visible=True)),
            inputs=None,
            outputs=[explainer_content, explainer_close_btn],
        )
        explainer_close_btn.click(
            fn=lambda: ("", gr.update(visible=False)),
            inputs=None,
            outputs=[explainer_content, explainer_close_btn],
        )
        bring_back_btn.click(
            fn=bring_back_prior,
            inputs=[prior_state],
            outputs=[
                previous_ribbon,
                sql_output,
                data_output,
                result_summary,
                prior_state,
                bring_back_btn,
            ],
        )

        submit_outputs = [
            previous_ribbon,
            result_summary,
            data_output,
            download_output,
            sql_output,
            status,
            first_visit,
            prior_state,
            has_asked,
            bring_back_btn,
            *[dd for dd, _ in starter_buttons],
        ]
        submit_btn.click(
            fn=on_submit,
            inputs=[user_input, prior_state, has_asked],
            outputs=submit_outputs,
        )
        user_input.submit(
            fn=on_submit,
            inputs=[user_input, prior_state, has_asked],
            outputs=submit_outputs,
        )

    return demo


if __name__ == "__main__":
    print("🤖 Loading model (Qwen2.5-Coder-14B bnb-4bit + LoRA)...")
    llm = load_model()
    print("✅ Ready.")
    demo = build_demo()
    demo.launch(css=CUSTOM_CSS, head=HEAD_HTML)
