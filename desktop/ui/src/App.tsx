import React, { useEffect, useState } from "react";
import {
  applyZeroLlmFilterBarMutation,
  PRESET_SCENARIOS,
  PresetScenario,
  runPresetOrPromptScenario,
  runPromptScenario,
  TwoHopTurnState,
} from "./lib/local-ai-provider";
import { FilterMutation } from "./schemas/workspace-ui";
import { WorkspaceRenderer } from "./components/registry/WorkspaceRenderer";

export const App: React.FC = () => {
  const [activeScenario, setActiveScenario] = useState<PresetScenario | null>(
    PRESET_SCENARIOS[0]
  );
  const [turnState, setTurnState] = useState<TwoHopTurnState | null>(null);
  const [baseRows, setBaseRows] = useState<Record<string, unknown>[]>([]);
  const [filterLatencyMs, setFilterLatencyMs] = useState<number | null>(null);
  const [showInspector, setShowInspector] = useState<boolean>(false);
  const [question, setQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeScenario) return;
    let cancelled = false;
    runPresetOrPromptScenario(activeScenario).then((state) => {
      if (!cancelled) {
        setTurnState(state);
        setBaseRows(state.dataset.rows);
        setFilterLatencyMs(null);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeScenario]);

  const handleAsk = async () => {
    const trimmed = question.trim();
    if (!trimmed || isAsking) return;
    setIsAsking(true);
    setAskError(null);
    try {
      const state = await runPromptScenario(trimmed);
      setActiveScenario(null);
      setTurnState(state);
      setBaseRows(state.dataset.rows);
      setFilterLatencyMs(null);
    } catch (err) {
      setAskError(err instanceof Error ? err.message : "Asking failed.");
    } finally {
      setIsAsking(false);
    }
  };

  const handleApplyFilters = async (filters: FilterMutation[]) => {
    if (!turnState) return;
    const { dataset, filterLatencyMs: elapsed } =
      await applyZeroLlmFilterBarMutation(turnState, baseRows, filters);
    setTurnState({
      ...turnState,
      dataset,
    });
    setFilterLatencyMs(elapsed);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="brand-title">
            Sovereign Local-First Analytics &amp; Generative UI Engine
          </h1>
          <p className="brand-subtitle">
            Tao + Wry Native Host • Medallion SQLite→DuckDB • Zero-Copy{" "}
            <code>arrow://</code> IPC • Two-Hop GBNF Agent
          </p>
        </div>
        {turnState && (
          <div className="telemetry-pills">
            <span className="telemetry-badge">
              Stream: <strong>arrow://{turnState.dataset.queryId}</strong> (
              {turnState.dataset.byteLength.toLocaleString()} B)
            </span>
            <span className="telemetry-badge">
              Arrow Decode: <strong>{turnState.dataset.decodeTimeMs}ms</strong>
            </span>
            <span className="telemetry-badge">
              Turn Latency: <strong>{turnState.latencyMs}ms</strong>
            </span>
          </div>
        )}
      </header>

      <nav className="scenario-bar" aria-label="Analytical Trajectories">
        <form
          className="ask-block"
          aria-label="Ask a question"
          onSubmit={(e) => {
            e.preventDefault();
            void handleAsk();
          }}
        >
          <label className="ask-label" htmlFor="ask-question">
            Ask a question
          </label>
          <div className="ask-input-row">
            <textarea
              id="ask-question"
              className="ask-textarea"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  void handleAsk();
                }
              }}
              placeholder="Ask in plain English… e.g. What is the average attendance rate by school?"
              rows={2}
              disabled={isAsking}
            />
            <button
              type="submit"
              className="ask-submit"
              disabled={isAsking || !question.trim()}
            >
              {isAsking ? "Asking…" : "Get answer"}
            </button>
          </div>
          <p className="ask-hint">
            ⌘/Ctrl + Enter to ask. If the desktop host is running, your question
            drives the two-hop SQL → UI agent loop.
          </p>
          {askError && (
            <p className="ask-error" role="alert">
              {askError}
            </p>
          )}
        </form>
        <div className="preset-row">
          {PRESET_SCENARIOS.map((scen) => (
            <button
              key={scen.id}
              type="button"
              className={`scenario-btn ${
                activeScenario?.id === scen.id ? "scenario-btn-active" : ""
              }`}
              onClick={() => {
                setAskError(null);
                setActiveScenario(scen);
              }}
            >
              [K-12] {scen.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="scenario-btn inspector-toggle"
          onClick={() => setShowInspector((prev) => !prev)}
        >
          {showInspector ? "Hide Two-Hop Inspector" : "Inspect Hop 1 SQL & Hop 2 JSON"}
        </button>
      </nav>

      {showInspector && turnState && (
        <section className="inspector-drawer" aria-label="Two-Hop Protocol Inspector">
          <div>
            <strong>Hop 1 Tool Call (execute_duckdb_query):</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.hop1Call, null, 2)}
            </pre>
          </div>
          <div>
            <strong>Turn 2 Tool Input (duckdb_result_summary):</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.resultSummary, null, 2)}
            </pre>
          </div>
          <div>
            <strong>Hop 2 Tool Call (render_workspace_ui):</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.hop2Call, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {turnState && (
        <WorkspaceRenderer
          uiPayload={turnState.hop2Call}
          resultSummary={turnState.resultSummary}
          rows={turnState.dataset.rows}
          baseRows={baseRows}
          onApplyFilters={handleApplyFilters}
          filterLatencyMs={filterLatencyMs}
        />
      )}
    </main>
  );
};
