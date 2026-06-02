"""API-level tests: agent CRUD, tool catalog, template seeding, run guarding."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_agent_crud():
    with TestClient(app) as client:
        # create
        r = client.post("/api/agents", json={"name": "Tester", "role": "qa",
                                              "tools": ["calculator"]})
        assert r.status_code == 201, r.text
        agent = r.json()
        assert agent["name"] == "Tester"
        aid = agent["id"]

        # read
        assert client.get(f"/api/agents/{aid}").json()["role"] == "qa"

        # update
        r = client.patch(f"/api/agents/{aid}", json={"role": "lead-qa"})
        assert r.json()["role"] == "lead-qa"

        # list contains it
        names = [a["name"] for a in client.get("/api/agents").json()]
        assert "Tester" in names

        # delete
        assert client.delete(f"/api/agents/{aid}").status_code == 204
        assert client.get(f"/api/agents/{aid}").status_code == 404


def test_tool_catalog_exposed():
    with TestClient(app) as client:
        tools = client.get("/api/agents/tools").json()
        names = {t["name"] for t in tools}
        assert {"web_search", "calculator", "http_get", "current_time"} <= names


def test_templates_are_seeded():
    with TestClient(app) as client:
        wfs = client.get("/api/workflows").json()
        names = {w["name"] for w in wfs}
        assert "Research & Review" in names
        assert "Customer Support Triage" in names
        # Each template has nodes + edges wired up.
        triage = next(w for w in wfs if w["name"] == "Customer Support Triage")
        assert len(triage["nodes"]) == 3
        assert len(triage["edges"]) >= 2


def test_run_blocked_without_api_key():
    """Safety: the run endpoint refuses to execute when no LLM key is set."""
    with TestClient(app) as client:
        wfs = client.get("/api/workflows").json()
        wf_id = wfs[0]["id"]
        r = client.post(f"/api/workflows/{wf_id}/run", json={"input_text": "hi"})
        assert r.status_code == 400
        assert "GOOGLE_API_KEY" in r.json()["detail"]
