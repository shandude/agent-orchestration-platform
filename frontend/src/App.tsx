import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { api, Meta } from "./api";
import AgentsPage from "./pages/AgentsPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import MonitorPage from "./pages/MonitorPage";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded-lg text-sm ${
      isActive ? "bg-accent text-white" : "text-white/70 hover:bg-white/5"
    }`;

  return (
    <div className="h-full flex flex-col">
      <header className="flex items-center gap-4 px-5 py-3 border-b border-white/10">
        <div className="font-semibold tracking-tight">
          ⬡ Agent Orchestration Platform
        </div>
        <nav className="flex gap-1">
          <NavLink to="/agents" className={linkCls}>
            Agents
          </NavLink>
          <NavLink to="/workflows" className={linkCls}>
            Workflows
          </NavLink>
          <NavLink to="/monitor" className={linkCls}>
            Live Monitor
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs">
          <Status ok={meta?.llm_enabled} label="Gemini" />
          <Status ok={meta?.telegram_enabled} label="Telegram" />
        </div>
      </header>
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/workflows" replace />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="/workflows/:id" element={<WorkflowsPage />} />
          <Route path="/monitor" element={<MonitorPage />} />
        </Routes>
      </main>
    </div>
  );
}

function Status({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          ok ? "bg-emerald-400" : "bg-white/25"
        }`}
      />
      {label}
    </span>
  );
}
