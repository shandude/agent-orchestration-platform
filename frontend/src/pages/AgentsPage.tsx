import { useEffect, useState } from "react";
import { Agent, ToolSpec, api } from "../api";

const EMPTY: Partial<Agent> = {
  name: "",
  role: "",
  system_prompt: "",
  model: "gemini-2.0-flash",
  tools: [],
  channels: [],
  skills: [],
  guardrails: [],
  interaction_rules: "",
  temperature: 0.3,
  max_tokens: 1024,
  memory_enabled: true,
  memory_window: 10,
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [editing, setEditing] = useState<Partial<Agent> | null>(null);

  const load = () => api.listAgents().then(setAgents);
  useEffect(() => {
    load();
    api.tools().then(setTools);
  }, []);

  const save = async () => {
    if (!editing?.name) return;
    if (editing.id) await api.updateAgent(editing.id, editing);
    else await api.createAgent(editing);
    setEditing(null);
    load();
  };

  return (
    <div className="h-full grid grid-cols-[360px_1fr] overflow-hidden">
      <div className="border-r border-white/10 overflow-y-auto p-4 space-y-2">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">Agents</h2>
          <button className="btn" onClick={() => setEditing({ ...EMPTY })}>
            + New
          </button>
        </div>
        {agents.map((a) => (
          <button
            key={a.id}
            onClick={() => setEditing(a)}
            className={`w-full text-left card hover:border-accent ${
              editing?.id === a.id ? "border-accent" : ""
            }`}
          >
            <div className="font-medium">{a.name}</div>
            <div className="text-xs text-white/50">{a.role || "—"}</div>
            <div className="flex flex-wrap gap-1 mt-2">
              {a.channels.map((c) => (
                <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                  {c}
                </span>
              ))}
              {a.tools.map((t) => (
                <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-white/10">
                  {t}
                </span>
              ))}
            </div>
          </button>
        ))}
      </div>

      <div className="overflow-y-auto p-6">
        {!editing ? (
          <div className="text-white/40 mt-10 text-center">
            Select an agent or create a new one to configure its personality,
            tools, memory and guardrails.
          </div>
        ) : (
          <div className="max-w-2xl space-y-4">
            <h3 className="font-semibold text-lg">
              {editing.id ? "Edit agent" : "New agent"}
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Name">
                <input className="input" value={editing.name ?? ""}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              </Field>
              <Field label="Role">
                <input className="input" value={editing.role ?? ""}
                  onChange={(e) => setEditing({ ...editing, role: e.target.value })} />
              </Field>
            </div>
            <Field label="System prompt / personality">
              <textarea className="input h-28" value={editing.system_prompt ?? ""}
                onChange={(e) => setEditing({ ...editing, system_prompt: e.target.value })} />
            </Field>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Model">
                <input className="input" value={editing.model ?? ""}
                  onChange={(e) => setEditing({ ...editing, model: e.target.value })} />
              </Field>
              <Field label="Temperature">
                <input type="number" step="0.1" className="input" value={editing.temperature ?? 0.3}
                  onChange={(e) => setEditing({ ...editing, temperature: parseFloat(e.target.value) })} />
              </Field>
              <Field label="Max tokens">
                <input type="number" className="input" value={editing.max_tokens ?? 1024}
                  onChange={(e) => setEditing({ ...editing, max_tokens: parseInt(e.target.value) })} />
              </Field>
            </div>

            <Field label="Tools">
              <div className="flex flex-wrap gap-2">
                {tools.map((t) => {
                  const on = editing.tools?.includes(t.name);
                  return (
                    <button key={t.name} title={t.description}
                      onClick={() =>
                        setEditing({
                          ...editing,
                          tools: on
                            ? editing.tools!.filter((x) => x !== t.name)
                            : [...(editing.tools ?? []), t.name],
                        })
                      }
                      className={`text-xs px-2 py-1 rounded-lg border ${
                        on ? "bg-accent border-accent" : "border-white/15"
                      }`}>
                      {t.name}
                    </button>
                  );
                })}
              </div>
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Channels (comma-sep)">
                <input className="input" value={(editing.channels ?? []).join(", ")}
                  onChange={(e) => setEditing({ ...editing, channels: splitList(e.target.value) })} />
              </Field>
              <Field label="Skills (comma-sep)">
                <input className="input" value={(editing.skills ?? []).join(", ")}
                  onChange={(e) => setEditing({ ...editing, skills: splitList(e.target.value) })} />
              </Field>
            </div>
            <Field label="Guardrails (one per line)">
              <textarea className="input h-20"
                value={(editing.guardrails ?? []).join("\n")}
                onChange={(e) => setEditing({ ...editing, guardrails: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })} />
            </Field>
            <Field label="Interaction rules">
              <input className="input" value={editing.interaction_rules ?? ""}
                onChange={(e) => setEditing({ ...editing, interaction_rules: e.target.value })} />
            </Field>
            <Field label="Memory window (messages)">
              <input type="number" className="input w-40" value={editing.memory_window ?? 10}
                onChange={(e) => setEditing({ ...editing, memory_window: parseInt(e.target.value) })} />
            </Field>

            <div className="flex gap-2 pt-2">
              <button className="btn" onClick={save}>Save</button>
              <button className="btn-ghost" onClick={() => setEditing(null)}>Cancel</button>
              {editing.id && (
                <button className="btn-ghost ml-auto text-red-300"
                  onClick={async () => { await api.deleteAgent(editing.id!); setEditing(null); load(); }}>
                  Delete
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}

function splitList(s: string): string[] {
  return s.split(",").map((x) => x.trim()).filter(Boolean);
}
