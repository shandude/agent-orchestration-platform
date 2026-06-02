import { useEffect, useState } from "react";
import { Agent, Run, Workflow, api } from "../api";
import WorkflowBuilder from "../components/WorkflowBuilder";
import { useMonitor } from "../hooks/useMonitor";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Workflow | null>(null);

  const load = async () => {
    const [wfs, ags] = await Promise.all([api.listWorkflows(), api.listAgents()]);
    setWorkflows(wfs);
    setAgents(ags);
    setSelected((cur) => (cur ? wfs.find((w) => w.id === cur.id) ?? wfs[0] : wfs[0]) ?? null);
  };
  useEffect(() => { load(); }, []);

  const createWf = async () => {
    const w = await api.createWorkflow({ name: "New workflow", nodes: [], edges: [] });
    await load();
    setSelected(w);
  };

  return (
    <div className="h-full grid grid-cols-[280px_1fr] overflow-hidden">
      <div className="border-r border-white/10 overflow-y-auto p-3 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-semibold">Workflows</h2>
          <button className="btn" onClick={createWf}>+ New</button>
        </div>
        {workflows.map((w) => (
          <button key={w.id} onClick={() => setSelected(w)}
            className={`w-full text-left card hover:border-accent ${selected?.id === w.id ? "border-accent" : ""}`}>
            <div className="font-medium flex items-center gap-2">
              {w.name}
              {w.is_template && <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/30">template</span>}
            </div>
            <div className="text-xs text-white/50 line-clamp-2 mt-1">{w.description || "—"}</div>
            <div className="text-[11px] text-white/40 mt-1">{w.nodes.length} nodes · {w.edges.length} edges</div>
          </button>
        ))}
      </div>

      {selected ? (
        <div className="grid grid-rows-[1fr_auto] overflow-hidden">
          <WorkflowBuilder
            key={selected.id}
            workflow={selected}
            agents={agents}
            onSaved={(w) => { setSelected(w); setWorkflows((ws) => ws.map((x) => (x.id === w.id ? w : x))); }}
          />
          <RunPanel workflow={selected} />
        </div>
      ) : (
        <div className="text-white/40 text-center mt-16">Create a workflow to begin.</div>
      )}
    </div>
  );
}

function RunPanel({ workflow }: { workflow: Workflow }) {
  const [input, setInput] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [running, setRunning] = useState(false);
  const { events } = useMonitor();

  // Watch the live stream for this run's completion + cost.
  const myEvents = run ? events.filter((e) => e.run_id === run.id) : [];
  const ended = myEvents.find((e) => e.type === "run_end");
  const lastCost = [...myEvents].reverse().find((e) => e.data?.total_cost_usd != null);

  const start = async () => {
    if (!input.trim()) return;
    setRunning(true);
    try {
      const r = await api.runWorkflow(workflow.id, input);
      setRun(r);
    } catch (e: any) {
      alert(e?.response?.data?.detail ?? "Run failed to start");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="border-t border-white/10 p-3 max-h-[42%] overflow-y-auto">
      <div className="flex gap-2">
        <input className="input" placeholder={`Ask "${workflow.name}" something…`}
          value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && start()} />
        <button className="btn" onClick={start} disabled={running}>Run</button>
      </div>

      {run && (
        <div className="mt-3 text-sm space-y-2">
          <div className="flex items-center gap-3 text-xs text-white/60">
            <span>run {run.id.slice(0, 8)}</span>
            <span>· {ended ? ended.data?.status : "running…"}</span>
            {lastCost && (
              <span>· {lastCost.data?.total_prompt_tokens! + lastCost.data?.total_completion_tokens!} tokens · ${Number(lastCost.data?.total_cost_usd).toFixed(6)}</span>
            )}
          </div>
          <div className="space-y-1">
            {myEvents.filter((e) => e.type === "message").map((e, i) => (
              <div key={i} className="card py-2">
                <div className="text-[11px] text-white/40">
                  {e.data?.role}{e.data?.agent_name ? ` · ${e.data.agent_name}` : ""}
                </div>
                <div className="whitespace-pre-wrap text-sm">{e.message}</div>
              </div>
            ))}
          </div>
          {ended?.data?.output_text && (
            <div className="card border-accent">
              <div className="label">Final answer</div>
              <div className="whitespace-pre-wrap">{ended.data.output_text}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
