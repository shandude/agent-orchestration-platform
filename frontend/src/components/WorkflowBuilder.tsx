import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import { Agent, EdgeCondition, Workflow, api } from "../api";

interface Props {
  workflow: Workflow;
  agents: Agent[];
  onSaved: (w: Workflow) => void;
}

type CondType = EdgeCondition["type"];

export default function WorkflowBuilder({ workflow, agents, onSaved }: Props) {
  const agentName = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a.name])),
    [agents]
  );

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [entry, setEntry] = useState<string | null>(workflow.entry_node);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);

  // Hydrate canvas from the stored workflow.
  useEffect(() => {
    setEntry(workflow.entry_node);
    setNodes(
      workflow.nodes.map((n) => ({
        id: n.id,
        position: n.position ?? { x: 0, y: 0 },
        data: { label: `${n.label || agentName[n.agent_id] || n.id}`, agentId: n.agent_id },
        style: nodeStyle(n.id === workflow.entry_node),
      }))
    );
    setEdges(
      workflow.edges.map((e, i) => ({
        id: `e${i}-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label: condLabel(e.condition),
        markerEnd: { type: MarkerType.ArrowClosed },
        data: { condition: e.condition },
        animated: e.condition.type !== "always",
      }))
    );
    setDirty(false);
  }, [workflow.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Recolor nodes when the entry changes.
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({ ...n, style: nodeStyle(n.id === entry) }))
    );
  }, [entry]);

  const onConnect = useCallback((c: Connection) => {
    setEdges((eds) =>
      addEdge(
        {
          ...c,
          id: `e-${c.source}-${c.target}-${Date.now()}`,
          label: "always",
          markerEnd: { type: MarkerType.ArrowClosed },
          data: { condition: { type: "always", value: "" } },
        },
        eds
      )
    );
    setDirty(true);
  }, []);

  const addNode = (agentId: string) => {
    const id = `${agentId.slice(0, 4)}-${Date.now().toString().slice(-4)}`;
    setNodes((nds) => [
      ...nds,
      {
        id,
        position: { x: 120 + Math.random() * 240, y: 80 + Math.random() * 200 },
        data: { label: agentName[agentId] || agentId, agentId },
        style: nodeStyle(false),
      },
    ]);
    if (!entry) setEntry(id);
    setDirty(true);
  };

  const updateEdgeCond = (edgeId: string, cond: EdgeCondition) => {
    setEdges((eds) =>
      eds.map((e) =>
        e.id === edgeId
          ? { ...e, label: condLabel(cond), animated: cond.type !== "always", data: { condition: cond } }
          : e
      )
    );
    setDirty(true);
  };

  const save = async () => {
    const payloadNodes = nodes.map((n) => ({
      id: n.id,
      agent_id: (n.data as any).agentId,
      label: (n.data as any).label,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    }));
    const payloadEdges = edges.map((e) => ({
      source: e.source,
      target: e.target,
      condition: (e.data as any)?.condition ?? { type: "always", value: "" },
    }));
    const updated = await api.updateWorkflow(workflow.id, {
      nodes: payloadNodes as any,
      edges: payloadEdges as any,
      entry_node: entry,
    });
    setDirty(false);
    onSaved(updated);
  };

  const selected = edges.find((e) => e.id === selectedEdge);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 p-2 border-b border-white/10 flex-wrap">
        <select
          className="input w-48"
          defaultValue=""
          onChange={(e) => { if (e.target.value) { addNode(e.target.value); e.target.value = ""; } }}
        >
          <option value="">+ Add agent node…</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <select className="input w-48" value={entry ?? ""} onChange={(e) => { setEntry(e.target.value || null); setDirty(true); }}>
          <option value="">Entry node…</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>{(n.data as any).label}</option>
          ))}
        </select>
        <button className="btn" onClick={save} disabled={!dirty}>
          {dirty ? "Save changes" : "Saved"}
        </button>
        <span className="text-xs text-white/40 ml-2">
          Drag from a node's handle to another to connect. Click an edge to set its condition.
        </span>
      </div>

      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={(ch) => { setNodes((nds) => applyNodeChanges(ch, nds)); if (ch.some((c) => c.type === "position")) setDirty(true); }}
          onEdgesChange={(ch) => { setEdges((eds) => applyEdgeChanges(ch, eds)); }}
          onConnect={onConnect}
          onEdgeClick={(_, e) => setSelectedEdge(e.id)}
          fitView
          colorMode="dark"
        >
          <Background />
          <Controls />
        </ReactFlow>

        {selected && (
          <div className="absolute top-3 right-3 card w-72 space-y-3">
            <div className="flex items-center justify-between">
              <div className="font-medium text-sm">Edge condition</div>
              <button className="text-white/40" onClick={() => setSelectedEdge(null)}>✕</button>
            </div>
            <div className="text-xs text-white/50">
              {labelFor(selected.source, nodes)} → {labelFor(selected.target, nodes)}
            </div>
            <div>
              <label className="label">Type</label>
              <select className="input"
                value={(selected.data as any).condition.type}
                onChange={(e) => updateEdgeCond(selected.id, { type: e.target.value as CondType, value: (selected.data as any).condition.value })}>
                <option value="always">always (unconditional)</option>
                <option value="contains">contains (keyword in output)</option>
                <option value="llm">llm (router decides)</option>
              </select>
            </div>
            {(selected.data as any).condition.type !== "always" && (
              <div>
                <label className="label">
                  {(selected.data as any).condition.type === "contains" ? "Keyword" : "When to take this branch"}
                </label>
                <input className="input"
                  value={(selected.data as any).condition.value}
                  onChange={(e) => updateEdgeCond(selected.id, { type: (selected.data as any).condition.type, value: e.target.value })} />
              </div>
            )}
            <button className="btn-ghost w-full text-red-300"
              onClick={() => { setEdges((eds) => eds.filter((x) => x.id !== selected.id)); setSelectedEdge(null); setDirty(true); }}>
              Delete edge
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function nodeStyle(isEntry: boolean): React.CSSProperties {
  return {
    background: isEntry ? "#1d2b54" : "#121a2e",
    color: "#e6ebff",
    border: `1px solid ${isEntry ? "#5b8cff" : "rgba(255,255,255,0.15)"}`,
    borderRadius: 10,
    padding: "8px 14px",
    fontSize: 13,
  };
}
function condLabel(c: EdgeCondition): string {
  if (c.type === "always") return "always";
  if (c.type === "contains") return `contains "${c.value}"`;
  return `llm: ${c.value || "decide"}`;
}
function labelFor(id: string, nodes: Node[]): string {
  return (nodes.find((n) => n.id === id)?.data as any)?.label ?? id;
}
