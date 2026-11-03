import React, { useEffect, useState } from "react";
import {
  applyZeroLlmFilterBarMutation,
  PRESET_SCENARIOS,
  PresetScenario,
  runPresetOrPromptScenario,
  TwoHopTurnState,
} from "./lib/local-ai-provider";
import { FilterMutation } from "./schemas/workspace-ui";
import { WorkspaceRenderer } from "./components/registry/WorkspaceRenderer";

export const App: React.FC = () => {
  const [activeScenario, setActiveScenario] = useState<PresetScenario>(
    PRESET_SCENARIOS[0]
  );
  const [turnState, setTurnState] = useState<TwoHopTurnState | null>(null);
  const [baseRows, setBaseRows] = useState<Record<string, unknown>[]>([]);
  const [filterLatencyMs, setFilterLatencyMs] = useState<number | null>(null);
  const [showInspector, setShowInspector] = useState<boolean>(false);

  useEffect(() => {
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
        {PRESET_SCENARIOS.map((scen) => (
          <button
            key={scen.id}
            type="button"
            className={`scenario-btn ${
              activeScenario.id === scen.id ? "scenario-btn-active" : ""
            }`}
            onClick={() => setActiveScenario(scen)}
          >
            [K-12] {scen.label}
          </button>
        ))}

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
