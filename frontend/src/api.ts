import axios from "axios";

// In dev, Vite proxies /api and /ws to the backend. In Docker, VITE_API_BASE
// is injected at build time.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export const http = axios.create({ baseURL: BASE });

// ── Types ─────────────────────────────────────────────────────────
export interface Agent {
  id: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  tools: string[];
  channels: string[];
  skills: string[];
  guardrails: string[];
  interaction_rules: string;
  temperature: number;
  max_tokens: number;
  memory_enabled: boolean;
  memory_window: number;
}

export interface EdgeCondition {
  type: "always" | "contains" | "llm";
  value: string;
}
export interface WFNode {
  id: string;
  agent_id: string;
  label: string;
  position: { x: number; y: number };
}
export interface WFEdge {
  source: string;
  target: string;
  condition: EdgeCondition;
}
export interface Workflow {
  id: string;
  name: string;
  description: string;
  is_template: boolean;
  nodes: WFNode[];
  edges: WFEdge[];
  entry_node: string | null;
}

export interface Message {
  id: string;
  run_id: string | null;
  role: string;
  agent_id: string | null;
  agent_name: string | null;
  content: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  created_at: string;
}
export interface Run {
  id: string;
  workflow_id: string;
  status: string;
  trigger: string;
  input_text: string;
  output_text: string;
  error: string | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost_usd: number;
  created_at: string;
  finished_at: string | null;
  messages?: Message[];
}

export interface ToolSpec {
  name: string;
  description: string;
}
export interface Meta {
  llm_enabled: boolean;
  telegram_enabled: boolean;
  default_model: string;
  max_graph_iterations: number;
}

// ── API calls ─────────────────────────────────────────────────────
export const api = {
  meta: () => http.get<Meta>("/api/meta").then((r) => r.data),
  tools: () => http.get<ToolSpec[]>("/api/agents/tools").then((r) => r.data),

  listAgents: () => http.get<Agent[]>("/api/agents").then((r) => r.data),
  createAgent: (a: Partial<Agent>) =>
    http.post<Agent>("/api/agents", a).then((r) => r.data),
  updateAgent: (id: string, a: Partial<Agent>) =>
    http.patch<Agent>(`/api/agents/${id}`, a).then((r) => r.data),
  deleteAgent: (id: string) => http.delete(`/api/agents/${id}`),

  listWorkflows: () => http.get<Workflow[]>("/api/workflows").then((r) => r.data),
  getWorkflow: (id: string) =>
    http.get<Workflow>(`/api/workflows/${id}`).then((r) => r.data),
  createWorkflow: (w: Partial<Workflow>) =>
    http.post<Workflow>("/api/workflows", w).then((r) => r.data),
  updateWorkflow: (id: string, w: Partial<Workflow>) =>
    http.patch<Workflow>(`/api/workflows/${id}`, w).then((r) => r.data),
  deleteWorkflow: (id: string) => http.delete(`/api/workflows/${id}`),
  runWorkflow: (id: string, input_text: string) =>
    http
      .post<Run>(`/api/workflows/${id}/run`, { input_text, trigger: "ui" })
      .then((r) => r.data),

  listRuns: () => http.get<Run[]>("/api/runs").then((r) => r.data),
  getRun: (id: string) => http.get<Run>(`/api/runs/${id}`).then((r) => r.data),
};
