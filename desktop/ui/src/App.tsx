import React, { useCallback, useEffect, useRef, useState } from "react";
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
  const [isLoadingPreset, setIsLoadingPreset] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [isFiltering, setIsFiltering] = useState(false);
  const [filterError, setFilterError] = useState<string | null>(null);
  const [statusAnnouncement, setStatusAnnouncement] = useState("");
  const filterSeqRef = useRef(0);

  useEffect(() => {
    if (!activeScenario) return;
    let cancelled = false;
    setIsLoadingPreset(true);
    setAskError(null);
    runPresetOrPromptScenario(activeScenario)
      .then((state) => {
        if (!cancelled) {
          setTurnState(state);
          setBaseRows(state.dataset.rows);
          setFilterLatencyMs(null);
          setStatusAnnouncement(
            `Loaded ${state.hop2Call.arguments.title} (${state.dataset.rows.length} rows).`
          );
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setAskError(
            err instanceof Error
              ? err.message
              : "Could not load the selected report."
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingPreset(false);
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
      setStatusAnnouncement(
        `Answer ready: ${state.hop2Call.arguments.title} (${state.dataset.rows.length} rows).`
      );
    } catch (err) {
      setAskError(err instanceof Error ? err.message : "Asking failed.");
    } finally {
      setIsAsking(false);
    }
  };

  const handleApplyFilters = useCallback(
    async (filters: FilterMutation[]) => {
      if (!turnState) return;
      const reqId = ++filterSeqRef.current;
      setIsFiltering(true);
      setFilterError(null);
      try {
        const { dataset, filterLatencyMs: elapsed } =
          await applyZeroLlmFilterBarMutation(turnState, baseRows, filters);
        if (reqId !== filterSeqRef.current) {
          return;
        }
        setTurnState((prev) => (prev ? { ...prev, dataset } : prev));
        setFilterLatencyMs(elapsed);
        setStatusAnnouncement(
          `Updated view to ${dataset.rows.length} matching records.`
        );
      } catch (err) {
        if (reqId === filterSeqRef.current) {
          setFilterError(
            err instanceof Error ? err.message : "Could not apply filters."
          );
        }
      } finally {
        if (reqId === filterSeqRef.current) {
          setIsFiltering(false);
        }
      }
    },
    [turnState, baseRows]
  );

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1 className="brand-title">District Student Analytics Workspace</h1>
          <p className="brand-subtitle">
            Private, on-device school &amp; student insights — student names are
            never shown or sent online
          </p>
        </div>
        {turnState && (
          <div className="telemetry-pills">
            {turnState.mode === "deterministic_demo" && (
              <span className="telemetry-badge demo-mode-badge">
                <strong>Demo Mode</strong> (Offline Sample Assistant)
              </span>
            )}
            <span className="telemetry-badge">
              Records shown:{" "}
              <strong>{turnState.dataset.rows.length.toLocaleString()}</strong>
            </span>
            <span className="telemetry-badge">
              Response time: <strong>{turnState.latencyMs}ms</strong>
            </span>
          </div>
        )}
      </header>

      <div role="status" aria-live="polite" className="sr-only">
        {statusAnnouncement}
      </div>

      <nav className="scenario-bar" aria-label="Starter Reports and Question Box">
        <form
          className="ask-block"
          aria-label="Ask a question"
          onSubmit={(e) => {
            e.preventDefault();
            void handleAsk();
          }}
        >
          <label className="ask-label" htmlFor="ask-question">
            Ask a question about your schools
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
              {isAsking ? "Looking up…" : "Get answer"}
            </button>
          </div>
          <p className="ask-hint">
            Press ⌘/Ctrl + Enter to submit, or choose one of the starter
            reports below.
          </p>
          {askError && (
            <p className="ask-error" role="alert">
              {askError}
            </p>
          )}
        </form>
        <div className="preset-row" role="group" aria-label="Starter reports">
          {PRESET_SCENARIOS.map((scen) => {
            const isSelected = activeScenario?.id === scen.id;
            return (
              <button
                key={scen.id}
                type="button"
                aria-pressed={isSelected}
                className={`scenario-btn ${
                  isSelected ? "scenario-btn-active" : ""
                }`}
                onClick={() => {
                  setAskError(null);
                  setActiveScenario(scen);
                }}
              >
                {scen.label}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          aria-expanded={showInspector}
          className="scenario-btn inspector-toggle"
          onClick={() => setShowInspector((prev) => !prev)}
        >
          {showInspector ? "Hide technical details" : "Show technical details"}
        </button>
      </nav>

      {isLoadingPreset && !turnState && (
        <div className="workspace-panel" role="status">
          Loading report…
        </div>
      )}

      {showInspector && turnState && (
        <section className="inspector-drawer" aria-label="Technical query details">
          <div>
            <strong>Generated SQL Query:</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.hop1Call, null, 2)}
            </pre>
          </div>
          <div>
            <strong>Result Summary:</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.resultSummary, null, 2)}
            </pre>
          </div>
          <div>
            <strong>Layout Specification:</strong>
            <pre className="inspector-code">
              {JSON.stringify(turnState.hop2Call, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {filterError && (
        <p className="ask-error" role="alert">
          {filterError}
        </p>
      )}

      {turnState && (
        <div aria-busy={isFiltering || isAsking || isLoadingPreset}>
          <WorkspaceRenderer
            uiPayload={turnState.hop2Call}
            resultSummary={turnState.resultSummary}
            explanation={turnState.hop1Call.arguments.explanation}
            sql={turnState.hop1Call.arguments.sql}
            rows={turnState.dataset.rows}
            baseRows={baseRows}
            onApplyFilters={handleApplyFilters}
            filterLatencyMs={filterLatencyMs}
          />
        </div>
      )}
    </main>
  );
};
