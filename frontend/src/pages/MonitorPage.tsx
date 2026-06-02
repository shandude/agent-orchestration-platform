import { useEffect, useState } from "react";
import { Run, api } from "../api";
import { MonitorEvent, useMonitor } from "../hooks/useMonitor";

const COLORS: Record<string, string> = {
  run_start: "text-sky-300",
  run_end: "text-emerald-300",
  node_start: "text-indigo-300",
  node_end: "text-indigo-200/70",
  tool_call: "text-amber-300",
  message: "text-white",
  cost: "text-fuchsia-300",
  error: "text-red-400",
};

export default function MonitorPage() {
  const { events, connected, clear } = useMonitor();
  const [runs, setRuns] = useState<Run[]>([]);

  useEffect(() => {
    api.listRuns().then(setRuns);
  }, [events.length]); // refresh history as new events arrive

  const totalCost = runs.reduce((s, r) => s + (r.total_cost_usd || 0), 0);
  const totalTokens = runs.reduce(
    (s, r) => s + r.total_prompt_tokens + r.total_completion_tokens,
    0
  );

  return (
    <div className="h-full grid grid-cols-[1fr_320px] overflow-hidden">
      <div className="flex flex-col overflow-hidden">
        <div className="flex items-center gap-3 p-3 border-b border-white/10">
          <span className={`flex items-center gap-1 text-sm ${connected ? "text-emerald-300" : "text-white/40"}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400" : "bg-white/30"}`} />
            {connected ? "Live" : "Reconnecting…"}
          </span>
          <span className="text-xs text-white/50">{events.length} events</span>
          <button className="btn-ghost ml-auto" onClick={clear}>Clear</button>
        </div>
        <div className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-1">
          {events.length === 0 && (
            <div className="text-white/30 mt-8 text-center font-sans">
              Waiting for activity… run a workflow or message the Telegram bot.
            </div>
          )}
          {events.map((e, i) => (
            <EventRow key={i} e={e} />
          ))}
        </div>
      </div>

      <div className="border-l border-white/10 overflow-y-auto p-3 space-y-3">
        <div className="card">
          <div className="label">Totals (all runs)</div>
          <div className="text-2xl font-semibold">${totalCost.toFixed(6)}</div>
          <div className="text-xs text-white/50">{totalTokens.toLocaleString()} tokens</div>
        </div>
        <div className="label">Recent runs</div>
        {runs.map((r) => (
          <div key={r.id} className="card py-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono">{r.id.slice(0, 8)}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                r.status === "completed" ? "bg-emerald-500/20 text-emerald-300"
                : r.status === "failed" ? "bg-red-500/20 text-red-300"
                : "bg-white/10"}`}>{r.status}</span>
            </div>
            <div className="text-[11px] text-white/50 mt-1">via {r.trigger}</div>
            <div className="text-xs mt-1 line-clamp-2">{r.input_text}</div>
            <div className="text-[11px] text-white/40 mt-1">${r.total_cost_usd.toFixed(6)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EventRow({ e }: { e: MonitorEvent }) {
  const cls = COLORS[e.type] ?? "text-white/70";
  const time = e.ts ? new Date(e.ts).toLocaleTimeString() : "";
  let detail = e.message ?? "";
  if (e.type === "cost") {
    detail = `tokens=${e.data?.total_prompt_tokens! + e.data?.total_completion_tokens!} cost=$${Number(e.data?.total_cost_usd).toFixed(6)}`;
  }
  return (
    <div className="flex gap-2">
      <span className="text-white/30 shrink-0">{time}</span>
      <span className={`shrink-0 ${cls}`}>[{e.type}]</span>
      <span className="text-white/80 break-all">{detail}</span>
    </div>
  );
}
