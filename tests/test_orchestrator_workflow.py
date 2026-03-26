"""
Test suite covering all API commands the orchestrator (Alfred) and agents would use.
Mirrors the curl-based workflow from the README.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

class TestAgents:
    async def test_list_agents(self, client: AsyncClient):
        r = await client.get("/api/agents")
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) == 5
        ids = {a["agent_id"] for a in agents}
        assert ids == {"alfred", "vio", "neo", "zeo", "seo"}

    async def test_get_agent_detail(self, client: AsyncClient):
        r = await client.get("/api/agents/vio")
        assert r.status_code == 200
        assert r.json()["name"] == "Vio"
        assert "stories" in r.json()

    async def test_get_nonexistent_agent(self, client: AsyncClient):
        r = await client.get("/api/agents/nobody")
        assert r.status_code == 404

    async def test_agent_has_llm_model(self, client: AsyncClient):
        r = await client.get("/api/agents/alfred")
        assert r.status_code == 200
        data = r.json()
        assert "llm_model" in data

    async def test_all_agents_have_specialties(self, client: AsyncClient):
        r = await client.get("/api/agents")
        for agent in r.json():
            assert "specialty" in agent


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class TestProjects:
    async def test_create_project(self, client: AsyncClient):
        r = await client.post("/api/projects", json={
            "name": "EventOps",
            "slug": "eventops",
            "repo_path": "/Users/nlavani/projects/eventops",
            "description": "Event operations platform",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "EventOps"
        assert data["slug"] == "eventops"
        assert data["id"] is not None

    async def test_list_projects(self, client: AsyncClient):
        await client.post("/api/projects", json={"name": "P1", "slug": "p1"})
        r = await client.get("/api/projects")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_get_project_detail(self, client: AsyncClient):
        create = await client.post("/api/projects", json={"name": "P2", "slug": "p2"})
        pid = create.json()["id"]
        r = await client.get(f"/api/projects/{pid}")
        assert r.status_code == 200
        assert "features" in r.json()

    async def test_get_nonexistent_project(self, client: AsyncClient):
        r = await client.get("/api/projects/9999")
        assert r.status_code == 404

    async def test_project_without_optional_fields(self, client: AsyncClient):
        r = await client.post("/api/projects", json={"name": "Minimal", "slug": "minimal"})
        assert r.status_code == 201
        data = r.json()
        assert data["repo_path"] is None
        assert data["description"] is None


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

class TestFeatures:
    async def _make_project(self, client: AsyncClient) -> int:
        r = await client.post("/api/projects", json={"name": "FP", "slug": "fp"})
        return r.json()["id"]

    async def test_create_feature(self, client: AsyncClient):
        pid = await self._make_project(client)
        r = await client.post("/api/features", json={
            "project_id": pid,
            "title": "User Login Flow",
            "description": "Full OAuth login",
        })
        assert r.status_code == 201
        assert r.json()["status"] == "planning"

    async def test_list_features_filter_by_status(self, client: AsyncClient):
        pid = await self._make_project(client)
        await client.post("/api/features", json={"project_id": pid, "title": "F1"})
        r = await client.get("/api/features", params={"status": "planning"})
        assert r.status_code == 200
        assert all(f["status"] == "planning" for f in r.json())

    async def test_list_features_filter_by_project(self, client: AsyncClient):
        pid = await self._make_project(client)
        await client.post("/api/features", json={"project_id": pid, "title": "F2"})
        r = await client.get("/api/features", params={"project_id": pid})
        assert r.status_code == 200

    async def test_get_feature_detail(self, client: AsyncClient):
        pid = await self._make_project(client)
        create = await client.post("/api/features", json={"project_id": pid, "title": "F3"})
        fid = create.json()["id"]
        r = await client.get(f"/api/features/{fid}")
        assert r.status_code == 200
        assert "stories" in r.json()

    async def test_update_feature_status(self, client: AsyncClient):
        pid = await self._make_project(client)
        create = await client.post("/api/features", json={"project_id": pid, "title": "F4"})
        fid = create.json()["id"]
        r = await client.patch(f"/api/features/{fid}", json={"status": "in_progress"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    async def test_complete_feature_sets_timestamp(self, client: AsyncClient):
        pid = await self._make_project(client)
        create = await client.post("/api/features", json={"project_id": pid, "title": "F5"})
        fid = create.json()["id"]
        r = await client.patch(f"/api/features/{fid}", json={"status": "complete"})
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

    async def test_invalid_feature_status(self, client: AsyncClient):
        pid = await self._make_project(client)
        create = await client.post("/api/features", json={"project_id": pid, "title": "F6"})
        fid = create.json()["id"]
        r = await client.patch(f"/api/features/{fid}", json={"status": "bogus"})
        assert r.status_code == 400

    async def test_get_nonexistent_feature(self, client: AsyncClient):
        r = await client.get("/api/features/9999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Stories -- creation, querying, and summary field
# ---------------------------------------------------------------------------

class TestStories:
    async def _make_feature(self, client: AsyncClient) -> int:
        p = await client.post("/api/projects", json={"name": "SP", "slug": "sp"})
        pid = p.json()["id"]
        f = await client.post("/api/features", json={"project_id": pid, "title": "SF"})
        return f.json()["id"]

    async def test_create_story(self, client: AsyncClient):
        fid = await self._make_feature(client)
        r = await client.post("/api/stories", json={
            "feature_id": fid,
            "title": "Login form UI",
            "assigned_to": "vio",
            "points": 3,
            "labels": "ui,frontend",
            "acceptance_criteria": "Form renders with email/password",
            "testing_criteria": "Visual inspection passes",
        })
        assert r.status_code == 201
        assert r.json()["status"] == "todo"
        assert r.json()["assigned_to"] == "vio"

    async def test_create_story_with_summary(self, client: AsyncClient):
        fid = await self._make_feature(client)
        r = await client.post("/api/stories", json={
            "feature_id": fid,
            "title": "Dashboard layout",
            "summary": "Build the main dashboard grid layout",
            "points": 5,
        })
        assert r.status_code == 201
        assert r.json()["summary"] == "Build the main dashboard grid layout"

    async def test_create_story_invalid_points(self, client: AsyncClient):
        fid = await self._make_feature(client)
        r = await client.post("/api/stories", json={
            "feature_id": fid,
            "title": "Bad points",
            "points": 4,
        })
        assert r.status_code == 400

    async def test_list_stories_filter_by_status(self, client: AsyncClient):
        fid = await self._make_feature(client)
        await client.post("/api/stories", json={"feature_id": fid, "title": "S1", "assigned_to": "neo", "points": 1})
        r = await client.get("/api/stories", params={"status": "todo"})
        assert r.status_code == 200
        assert all(s["status"] == "todo" for s in r.json())

    async def test_list_stories_filter_by_agent(self, client: AsyncClient):
        fid = await self._make_feature(client)
        await client.post("/api/stories", json={"feature_id": fid, "title": "S2", "assigned_to": "zeo", "points": 2})
        r = await client.get("/api/stories", params={"assigned_to": "zeo"})
        assert r.status_code == 200
        assert all(s["assigned_to"] == "zeo" for s in r.json())

    async def test_list_stories_filter_by_feature(self, client: AsyncClient):
        fid = await self._make_feature(client)
        await client.post("/api/stories", json={"feature_id": fid, "title": "S3", "points": 1})
        r = await client.get("/api/stories", params={"feature_id": fid})
        assert r.status_code == 200
        assert all(s["feature_id"] == fid for s in r.json())

    async def test_get_story_detail_with_comments(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S3", "points": 1})
        sid = create.json()["id"]
        r = await client.get(f"/api/stories/{sid}")
        assert r.status_code == 200
        assert "comments" in r.json()

    async def test_update_story_fields(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S4", "points": 1})
        sid = create.json()["id"]
        r = await client.patch(f"/api/stories/{sid}", json={
            "pr_url": "https://github.com/org/repo/pull/42",
            "labels": "backend,auth",
        })
        assert r.status_code == 200
        assert r.json()["pr_url"] == "https://github.com/org/repo/pull/42"

    async def test_update_story_summary(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S5", "points": 2})
        sid = create.json()["id"]
        r = await client.patch(f"/api/stories/{sid}", json={"summary": "Updated mini description"})
        assert r.status_code == 200
        assert r.json()["summary"] == "Updated mini description"

    async def test_update_story_acceptance_and_testing_criteria(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S6", "points": 1})
        sid = create.json()["id"]
        r = await client.patch(f"/api/stories/{sid}", json={
            "acceptance_criteria": "All tests pass, code reviewed",
            "testing_criteria": "Unit tests + integration tests",
        })
        assert r.status_code == 200
        assert r.json()["acceptance_criteria"] == "All tests pass, code reviewed"
        assert r.json()["testing_criteria"] == "Unit tests + integration tests"

    async def test_update_story_description(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S7", "points": 1})
        sid = create.json()["id"]
        r = await client.patch(f"/api/stories/{sid}", json={"description": "Detailed description here"})
        assert r.status_code == 200
        assert r.json()["description"] == "Detailed description here"

    async def test_update_story_points(self, client: AsyncClient):
        fid = await self._make_feature(client)
        create = await client.post("/api/stories", json={"feature_id": fid, "title": "S8", "points": 1})
        sid = create.json()["id"]
        r = await client.patch(f"/api/stories/{sid}", json={"points": 5})
        assert r.status_code == 200
        assert r.json()["points"] == 5

    async def test_get_nonexistent_story(self, client: AsyncClient):
        r = await client.get("/api/stories/9999")
        assert r.status_code == 404

    async def test_update_nonexistent_story(self, client: AsyncClient):
        r = await client.patch("/api/stories/9999", json={"title": "Nope"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Story transitions (column moves)
# ---------------------------------------------------------------------------

class TestStoryTransitions:
    async def _make_story(self, client: AsyncClient, assigned_to: str = "vio") -> int:
        p = await client.post("/api/projects", json={"name": "TP", "slug": "tp"})
        f = await client.post("/api/features", json={"project_id": p.json()["id"], "title": "TF"})
        s = await client.post("/api/stories", json={
            "feature_id": f.json()["id"],
            "title": "Test Story",
            "assigned_to": assigned_to,
            "points": 2,
        })
        return s.json()["id"]

    async def test_assigned_agent_moves_todo_to_in_progress(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "vio"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"
        assert r.json()["started_at"] is not None

    async def test_wrong_agent_cannot_move(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "neo"})
        assert r.status_code == 403

    async def test_full_cycle_todo_to_done(self, client: AsyncClient):
        sid = await self._make_story(client, "neo")
        await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "neo"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "neo"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "review", "agent_id": "neo"})

        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "done", "agent_id": "alfred"})
        assert r.status_code == 200
        assert r.json()["status"] == "done"
        assert r.json()["completed_at"] is not None

    async def test_non_alfred_cannot_move_to_done(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "review", "agent_id": "vio"})

        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "done", "agent_id": "vio"})
        assert r.status_code == 403
        assert "alfred" in r.json()["detail"].lower()

    async def test_alfred_can_reject_review_to_in_progress(self, client: AsyncClient):
        sid = await self._make_story(client, "zeo")
        await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "zeo"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "zeo"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "review", "agent_id": "zeo"})

        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "alfred"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    async def test_invalid_transition(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "done", "agent_id": "vio"})
        assert r.status_code == 400

    async def test_invalid_status_value(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "garbage", "agent_id": "vio"})
        assert r.status_code == 400

    async def test_move_nonexistent_story(self, client: AsyncClient):
        r = await client.patch("/api/stories/9999/move", json={"status": "in_progress", "agent_id": "vio"})
        assert r.status_code == 404

    async def test_started_at_only_set_on_first_in_progress(self, client: AsyncClient):
        sid = await self._make_story(client, "vio")
        r1 = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "vio"})
        first_started = r1.json()["started_at"]

        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "review", "agent_id": "vio"})
        r2 = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "alfred"})
        assert r2.json()["started_at"] == first_started


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class TestComments:
    async def _make_story(self, client: AsyncClient) -> int:
        p = await client.post("/api/projects", json={"name": "CP", "slug": "cp"})
        f = await client.post("/api/features", json={"project_id": p.json()["id"], "title": "CF"})
        s = await client.post("/api/stories", json={
            "feature_id": f.json()["id"], "title": "CS", "assigned_to": "vio", "points": 1,
        })
        return s.json()["id"]

    async def test_add_comment(self, client: AsyncClient):
        sid = await self._make_story(client)
        r = await client.post(f"/api/stories/{sid}/comments", json={
            "author": "vio",
            "content": "Starting work on this story.",
        })
        assert r.status_code == 201
        assert r.json()["author"] == "vio"
        assert r.json()["story_id"] == sid

    async def test_comments_appear_in_story_detail(self, client: AsyncClient):
        sid = await self._make_story(client)
        await client.post(f"/api/stories/{sid}/comments", json={"author": "vio", "content": "Update 1"})
        await client.post(f"/api/stories/{sid}/comments", json={"author": "alfred", "content": "Looks good"})

        r = await client.get(f"/api/stories/{sid}")
        assert r.status_code == 200
        comments = r.json()["comments"]
        assert len(comments) == 2
        assert comments[0]["author"] == "vio"
        assert comments[1]["author"] == "alfred"

    async def test_comment_on_nonexistent_story(self, client: AsyncClient):
        r = await client.post("/api/stories/9999/comments", json={"author": "vio", "content": "Nope"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Board & History
# ---------------------------------------------------------------------------

class TestBoard:
    async def _setup_board(self, client: AsyncClient) -> dict:
        p = await client.post("/api/projects", json={"name": "BP", "slug": "bp"})
        pid = p.json()["id"]
        f = await client.post("/api/features", json={"project_id": pid, "title": "BF"})
        fid = f.json()["id"]

        s1 = await client.post("/api/stories", json={"feature_id": fid, "title": "Todo story", "assigned_to": "vio", "points": 1})
        s2 = await client.post("/api/stories", json={"feature_id": fid, "title": "WIP story", "assigned_to": "neo", "points": 2})
        sid2 = s2.json()["id"]
        await client.patch(f"/api/stories/{sid2}/move", json={"status": "in_progress", "agent_id": "neo"})

        return {"project_id": pid, "feature_id": fid, "story1_id": s1.json()["id"], "story2_id": sid2}

    async def test_board_returns_all_columns(self, client: AsyncClient):
        await self._setup_board(client)
        r = await client.get("/api/board")
        assert r.status_code == 200
        columns = r.json()["columns"]
        statuses = [c["status"] for c in columns]
        assert statuses == ["todo", "in_progress", "testing", "review", "done"]

    async def test_board_filter_by_project(self, client: AsyncClient):
        data = await self._setup_board(client)
        r = await client.get("/api/board", params={"project_id": data["project_id"]})
        assert r.status_code == 200
        total_stories = sum(len(c["stories"]) for c in r.json()["columns"])
        assert total_stories == 2

    async def test_board_stories_in_correct_columns(self, client: AsyncClient):
        data = await self._setup_board(client)
        r = await client.get("/api/board")
        columns = {c["status"]: c["stories"] for c in r.json()["columns"]}
        todo_ids = [s["id"] for s in columns["todo"]]
        wip_ids = [s["id"] for s in columns["in_progress"]]
        assert data["story1_id"] in todo_ids
        assert data["story2_id"] in wip_ids

    async def test_history_empty_initially(self, client: AsyncClient):
        r = await client.get("/api/history")
        assert r.status_code == 200
        assert r.json() == []

    async def test_history_shows_completed_features(self, client: AsyncClient):
        p = await client.post("/api/projects", json={"name": "HP", "slug": "hp"})
        f = await client.post("/api/features", json={"project_id": p.json()["id"], "title": "HF"})
        fid = f.json()["id"]

        s = await client.post("/api/stories", json={"feature_id": fid, "title": "HS", "assigned_to": "vio", "points": 1})
        sid = s.json()["id"]
        await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "review", "agent_id": "vio"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "done", "agent_id": "alfred"})

        await client.patch(f"/api/features/{fid}", json={"status": "complete"})

        r = await client.get("/api/history")
        assert r.status_code == 200
        assert len(r.json()) >= 1
        assert r.json()[0]["stories"][0]["status"] == "done"


# ---------------------------------------------------------------------------
# Human drag-and-drop move (no agent_id restriction)
# ---------------------------------------------------------------------------

class TestHumanMove:
    async def _make_story(self, client: AsyncClient) -> int:
        p = await client.post("/api/projects", json={"name": "HMP", "slug": "hmp"})
        f = await client.post("/api/features", json={"project_id": p.json()["id"], "title": "HMF"})
        s = await client.post("/api/stories", json={
            "feature_id": f.json()["id"], "title": "Drag story", "assigned_to": "vio", "points": 1,
        })
        return s.json()["id"]

    async def test_human_can_move_story(self, client: AsyncClient):
        sid = await self._make_story(client)
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "human"})
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    async def test_human_can_skip_columns(self, client: AsyncClient):
        sid = await self._make_story(client)
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "done", "agent_id": "human"})
        assert r.status_code == 200
        assert r.json()["status"] == "done"

    async def test_human_can_move_backwards(self, client: AsyncClient):
        sid = await self._make_story(client)
        await client.patch(f"/api/stories/{sid}/move", json={"status": "in_progress", "agent_id": "human"})
        await client.patch(f"/api/stories/{sid}/move", json={"status": "testing", "agent_id": "human"})
        r = await client.patch(f"/api/stories/{sid}/move", json={"status": "todo", "agent_id": "human"})
        assert r.status_code == 200
        assert r.json()["status"] == "todo"


# ---------------------------------------------------------------------------
# ChitChat — Posts
# ---------------------------------------------------------------------------

class TestChitChatPosts:
    async def test_create_post(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "vio",
            "content": "Just finished a tricky CSS layout!",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["author"] == "vio"
        assert data["content"] == "Just finished a tricky CSS layout!"
        assert data["id"] is not None
        assert data["replies"] == []
        assert data["upvotes"] == []

    async def test_create_post_with_image(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "neo",
            "content": "Check out this architecture diagram",
            "image_url": "https://example.com/diagram.png",
        })
        assert r.status_code == 201
        assert r.json()["image_url"] == "https://example.com/diagram.png"

    async def test_create_post_with_link(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "seo",
            "content": "Found a great article on multi-agent setups",
            "link_url": "https://example.com/article",
            "link_title": "Multi-Agent Architecture Guide",
        })
        assert r.status_code == 201
        assert r.json()["link_url"] == "https://example.com/article"
        assert r.json()["link_title"] == "Multi-Agent Architecture Guide"

    async def test_create_post_with_mentions(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "neo",
            "content": "Hey @alfred, what do you think?",
            "mentions": "alfred",
        })
        assert r.status_code == 201
        assert r.json()["mentions"] == "alfred"

    async def test_create_post_with_multiple_mentions(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "vio",
            "content": "Team discussion needed",
            "mentions": "neo,zeo,alfred",
        })
        assert r.status_code == 201
        assert r.json()["mentions"] == "neo,zeo,alfred"

    async def test_create_post_without_mentions(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "zeo",
            "content": "Just thinking out loud",
        })
        assert r.status_code == 201
        assert r.json()["mentions"] is None

    async def test_create_post_with_local_image(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "vio",
            "content": "Saved this palette locally",
            "image_url": "/static/chitchat_images/palette.png",
        })
        assert r.status_code == 201
        assert r.json()["image_url"] == "/static/chitchat_images/palette.png"

    async def test_list_posts(self, client: AsyncClient):
        await client.post("/api/chitchat", json={"author": "vio", "content": "Post 1"})
        await client.post("/api/chitchat", json={"author": "neo", "content": "Post 2"})
        r = await client.get("/api/chitchat")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    async def test_list_posts_filter_by_author(self, client: AsyncClient):
        await client.post("/api/chitchat", json={"author": "vio", "content": "Vio here"})
        await client.post("/api/chitchat", json={"author": "neo", "content": "Neo here"})
        r = await client.get("/api/chitchat", params={"author": "vio"})
        assert r.status_code == 200
        assert all(p["author"] == "vio" for p in r.json())

    async def test_list_posts_pagination(self, client: AsyncClient):
        for i in range(3):
            await client.post("/api/chitchat", json={"author": "zeo", "content": f"Post {i}"})
        r = await client.get("/api/chitchat", params={"limit": 2, "offset": 0})
        assert r.status_code == 200
        assert len(r.json()) == 2

        r2 = await client.get("/api/chitchat", params={"limit": 2, "offset": 2})
        assert r2.status_code == 200
        assert len(r2.json()) >= 1

    async def test_get_single_post(self, client: AsyncClient):
        create = await client.post("/api/chitchat", json={"author": "alfred", "content": "Strategy update"})
        post_id = create.json()["id"]
        r = await client.get(f"/api/chitchat/{post_id}")
        assert r.status_code == 200
        assert r.json()["content"] == "Strategy update"

    async def test_get_nonexistent_post(self, client: AsyncClient):
        r = await client.get("/api/chitchat/9999")
        assert r.status_code == 404

    async def test_daily_post_limit(self, client: AsyncClient):
        for i in range(5):
            r = await client.post("/api/chitchat", json={"author": "seo", "content": f"Post {i}"})
            assert r.status_code == 201

        r = await client.post("/api/chitchat", json={"author": "seo", "content": "One too many"})
        assert r.status_code == 429
        assert "limit" in r.json()["detail"].lower()

    async def test_daily_limit_per_agent(self, client: AsyncClient):
        for i in range(5):
            await client.post("/api/chitchat", json={"author": "neo", "content": f"Neo {i}"})

        r_neo = await client.post("/api/chitchat", json={"author": "neo", "content": "Neo blocked"})
        assert r_neo.status_code == 429

        r_vio = await client.post("/api/chitchat", json={"author": "vio", "content": "Vio is fine"})
        assert r_vio.status_code == 201


# ---------------------------------------------------------------------------
# ChitChat — Replies
# ---------------------------------------------------------------------------

class TestChitChatReplies:
    async def _make_post(self, client: AsyncClient) -> int:
        r = await client.post("/api/chitchat", json={"author": "vio", "content": "Original post"})
        return r.json()["id"]

    async def test_add_reply(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "neo",
            "content": "Great thought!",
        })
        assert r.status_code == 201
        assert r.json()["author"] == "neo"
        assert r.json()["post_id"] == post_id

    async def test_replies_appear_in_post(self, client: AsyncClient):
        post_id = await self._make_post(client)
        await client.post(f"/api/chitchat/{post_id}/replies", json={"author": "neo", "content": "Reply 1"})
        await client.post(f"/api/chitchat/{post_id}/replies", json={"author": "zeo", "content": "Reply 2"})

        r = await client.get(f"/api/chitchat/{post_id}")
        assert len(r.json()["replies"]) == 2

    async def test_human_can_reply(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "human",
            "content": "Nice work, team!",
        })
        assert r.status_code == 201
        assert r.json()["author"] == "human"

    async def test_reply_with_mentions(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "zeo",
            "content": "@neo @vio let's discuss",
            "mentions": "neo,vio",
        })
        assert r.status_code == 201
        assert r.json()["mentions"] == "neo,vio"

    async def test_reply_without_mentions(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "alfred",
            "content": "Good observation",
        })
        assert r.status_code == 201
        assert r.json()["mentions"] is None

    async def test_reply_mentions_appear_in_post_detail(self, client: AsyncClient):
        post_id = await self._make_post(client)
        await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "neo",
            "content": "Tagging @alfred",
            "mentions": "alfred",
        })
        r = await client.get(f"/api/chitchat/{post_id}")
        replies = r.json()["replies"]
        assert len(replies) == 1
        assert replies[0]["mentions"] == "alfred"

    async def test_reply_to_nonexistent_post(self, client: AsyncClient):
        r = await client.post("/api/chitchat/9999/replies", json={"author": "vio", "content": "Nope"})
        assert r.status_code == 404

    async def test_daily_reply_limit(self, client: AsyncClient):
        post_id = await self._make_post(client)
        for i in range(20):
            r = await client.post(f"/api/chitchat/{post_id}/replies", json={
                "author": "alfred",
                "content": f"Reply {i}",
            })
            assert r.status_code == 201

        r = await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "alfred",
            "content": "One too many",
        })
        assert r.status_code == 429


# ---------------------------------------------------------------------------
# ChitChat — Upvotes
# ---------------------------------------------------------------------------

class TestChitChatUpvotes:
    async def _make_post(self, client: AsyncClient) -> int:
        r = await client.post("/api/chitchat", json={"author": "vio", "content": "Upvotable post"})
        return r.json()["id"]

    async def test_upvote_post(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "neo"})
        assert r.status_code == 201
        assert r.json()["agent_id"] == "neo"
        assert r.json()["post_id"] == post_id

    async def test_duplicate_upvote_rejected(self, client: AsyncClient):
        post_id = await self._make_post(client)
        await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "neo"})
        r = await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "neo"})
        assert r.status_code == 409

    async def test_multiple_agents_can_upvote(self, client: AsyncClient):
        post_id = await self._make_post(client)
        await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "neo"})
        await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "zeo"})
        await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "alfred"})

        r = await client.get(f"/api/chitchat/{post_id}")
        assert len(r.json()["upvotes"]) == 3

    async def test_remove_upvote(self, client: AsyncClient):
        post_id = await self._make_post(client)
        await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "neo"})
        r = await client.delete(f"/api/chitchat/{post_id}/upvote/neo")
        assert r.status_code == 204

        post = await client.get(f"/api/chitchat/{post_id}")
        assert len(post.json()["upvotes"]) == 0

    async def test_remove_nonexistent_upvote(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r = await client.delete(f"/api/chitchat/{post_id}/upvote/nobody")
        assert r.status_code == 404

    async def test_upvote_nonexistent_post(self, client: AsyncClient):
        r = await client.post("/api/chitchat/9999/upvote", json={"agent_id": "vio"})
        assert r.status_code == 404

    async def test_human_upvote_and_toggle(self, client: AsyncClient):
        post_id = await self._make_post(client)
        r1 = await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "human"})
        assert r1.status_code == 201
        assert r1.json()["agent_id"] == "human"

        r2 = await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "human"})
        assert r2.status_code == 409

        r3 = await client.delete(f"/api/chitchat/{post_id}/upvote/human")
        assert r3.status_code == 204

        r4 = await client.post(f"/api/chitchat/{post_id}/upvote", json={"agent_id": "human"})
        assert r4.status_code == 201


# ---------------------------------------------------------------------------
# Guides — CRUD and filtering
# ---------------------------------------------------------------------------

class TestGuides:
    async def test_list_seeded_guides(self, client: AsyncClient):
        r = await client.get("/api/guides")
        assert r.status_code == 200
        guides = r.json()
        assert len(guides) >= 5
        slugs = {g["slug"] for g in guides}
        assert "kanban-overview" in slugs

    async def test_get_guide_by_slug(self, client: AsyncClient):
        r = await client.get("/api/guides/kanban-overview")
        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "kanban-overview"
        assert data["title"] == "How the Kanban Board Works"
        assert "content" in data
        assert len(data["content"]) > 50

    async def test_get_nonexistent_guide(self, client: AsyncClient):
        r = await client.get("/api/guides/does-not-exist")
        assert r.status_code == 404

    async def test_filter_guides_by_category(self, client: AsyncClient):
        r = await client.get("/api/guides", params={"category": "workflow"})
        assert r.status_code == 200
        for g in r.json():
            assert g["category"] == "workflow"

    async def test_filter_guides_by_audience(self, client: AsyncClient):
        r = await client.get("/api/guides", params={"audience": "agents"})
        assert r.status_code == 200
        for g in r.json():
            assert g["audience"] in ("agents", "all")

    async def test_create_guide(self, client: AsyncClient):
        r = await client.post("/api/guides", json={
            "slug": "test-new-guide",
            "title": "Test Guide",
            "category": "workflow",
            "audience": "all",
            "content": "# Test\n\nThis is a test guide.",
            "sort_order": 99,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == "test-new-guide"
        assert data["title"] == "Test Guide"
        assert "content" in data

    async def test_create_duplicate_slug_rejected(self, client: AsyncClient):
        await client.post("/api/guides", json={
            "slug": "unique-slug",
            "title": "First",
            "category": "workflow",
            "content": "content",
        })
        r = await client.post("/api/guides", json={
            "slug": "unique-slug",
            "title": "Duplicate",
            "category": "workflow",
            "content": "other content",
        })
        assert r.status_code == 409

    async def test_update_guide(self, client: AsyncClient):
        await client.post("/api/guides", json={
            "slug": "updatable-guide",
            "title": "Original Title",
            "category": "reference",
            "content": "Original content",
        })
        r = await client.patch("/api/guides/updatable-guide", json={
            "title": "Updated Title",
            "content": "Updated content here",
        })
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Title"
        assert r.json()["content"] == "Updated content here"

    async def test_update_nonexistent_guide(self, client: AsyncClient):
        r = await client.patch("/api/guides/nope", json={"title": "Nope"})
        assert r.status_code == 404

    async def test_guide_summary_in_list(self, client: AsyncClient):
        r = await client.get("/api/guides")
        assert r.status_code == 200
        for g in r.json():
            assert "summary" in g
            assert "content" not in g

    async def test_guide_full_content_in_detail(self, client: AsyncClient):
        r = await client.get("/api/guides/kanban-overview")
        assert r.status_code == 200
        assert "content" in r.json()
        assert "summary" in r.json()


# ---------------------------------------------------------------------------
# Web Views — smoke tests (all pages return 200)
# ---------------------------------------------------------------------------

class TestWebViews:
    async def test_board_view(self, client: AsyncClient):
        r = await client.get("/")
        assert r.status_code == 200
        assert "Kanban Board" in r.text

    async def test_board_view_empty_project_filter(self, client: AsyncClient):
        r = await client.get("/", params={"project_id": ""})
        assert r.status_code == 200

    async def test_projects_view(self, client: AsyncClient):
        r = await client.get("/projects")
        assert r.status_code == 200

    async def test_features_view(self, client: AsyncClient):
        r = await client.get("/features")
        assert r.status_code == 200

    async def test_agents_view(self, client: AsyncClient):
        r = await client.get("/agents")
        assert r.status_code == 200
        assert "Alfred" in r.text

    async def test_chitchat_view(self, client: AsyncClient):
        r = await client.get("/chitchat")
        assert r.status_code == 200
        assert "ChitChat" in r.text

    async def test_guides_view(self, client: AsyncClient):
        r = await client.get("/guides")
        assert r.status_code == 200
        assert "Guides" in r.text

    async def test_guides_view_filter_by_category(self, client: AsyncClient):
        r = await client.get("/guides", params={"category": "workflow"})
        assert r.status_code == 200

    async def test_guide_detail_view(self, client: AsyncClient):
        r = await client.get("/guides/kanban-overview")
        assert r.status_code == 200
        assert "Kanban" in r.text

    async def test_history_view(self, client: AsyncClient):
        r = await client.get("/history")
        assert r.status_code == 200

    async def test_chitchat_images_directory_accessible(self, client: AsyncClient):
        from app.config import STATIC_DIR
        images_dir = STATIC_DIR / "chitchat_images"
        assert images_dir.exists()
        assert images_dir.is_dir()

    async def test_chitchat_guide_mentions_section(self, client: AsyncClient):
        r = await client.get("/api/guides/chitchat-rules")
        assert r.status_code == 200
        content = r.json()["content"]
        assert "@Mentions" in content or "mentions" in content.lower()
        assert "human" in content.lower()
        assert "chitchat_images" in content

    async def test_chitchat_view_has_tab_toggle(self, client: AsyncClient):
        r = await client.get("/chitchat")
        assert r.status_code == 200
        assert "Collaboration" in r.text
        assert "Conversation" in r.text
        assert "tab-collaboration" in r.text
        assert "tab-conversation" in r.text

    async def test_collaboration_guide_exists(self, client: AsyncClient):
        r = await client.get("/api/guides/collaboration")
        assert r.status_code == 200
        data = r.json()
        assert "Cross-Agent" in data["title"]
        assert "collab" in data["content"].lower()
        assert "story_id" in data["content"]


class TestCollabPosts:
    """Test collaboration post CRUD and rate limits."""

    async def test_create_collab_post(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "vio",
            "subject": "Need API contract for /auth/login",
            "story_id": 1,
            "body": "I need the response shape for the login endpoint.",
            "mentions": "neo",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["subject"] == "Need API contract for /auth/login"
        assert data["mentions"] == "neo"
        assert data["story_id"] == 1
        assert data["resolved"] == 0

    async def test_collab_post_requires_mentions(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "vio",
            "subject": "Test",
            "body": "Test body",
            "mentions": "",
        })
        assert r.status_code == 422

    async def test_list_collab_posts(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "neo",
            "subject": "DB schema question",
            "body": "What tables do you need?",
            "mentions": "zeo",
        })
        r = await client.get("/api/collab")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_filter_collab_by_mentioned(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "vio",
            "subject": "CSS help",
            "body": "Need help with layout",
            "mentions": "alfred",
        })
        r = await client.get("/api/collab", params={"mentioned": "alfred"})
        assert r.status_code == 200
        posts = r.json()
        assert all("alfred" in p["mentions"] for p in posts)

    async def test_filter_collab_by_story_id(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "neo",
            "subject": "Story 42 question",
            "story_id": 42,
            "body": "Is story 42 ready?",
            "mentions": "vio",
        })
        r = await client.get("/api/collab", params={"story_id": 42})
        assert r.status_code == 200
        posts = r.json()
        assert all(p["story_id"] == 42 for p in posts)

    async def test_resolve_collab_post(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "neo",
            "subject": "Resolve test",
            "body": "This will be resolved",
            "mentions": "vio",
        })
        post_id = r.json()["id"]
        r2 = await client.patch(f"/api/collab/{post_id}", json={"resolved": 1})
        assert r2.status_code == 200
        assert r2.json()["resolved"] == 1

    async def test_get_single_collab_post(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "zeo",
            "subject": "Single post test",
            "body": "Details here",
            "mentions": "neo",
        })
        post_id = r.json()["id"]
        r2 = await client.get(f"/api/collab/{post_id}")
        assert r2.status_code == 200
        assert r2.json()["subject"] == "Single post test"

    async def test_collab_post_not_found(self, client: AsyncClient):
        r = await client.get("/api/collab/99999")
        assert r.status_code == 404


class TestCollabReplies:
    """Test collaboration replies."""

    async def test_reply_to_collab_post(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "vio",
            "subject": "Reply test thread",
            "body": "Need input",
            "mentions": "neo",
        })
        post_id = r.json()["id"]

        r2 = await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "neo",
            "content": "Here's the info you need.",
        })
        assert r2.status_code == 201
        assert r2.json()["author"] == "neo"
        assert r2.json()["post_id"] == post_id

    async def test_reply_with_mentions(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "vio",
            "subject": "Mentions reply test",
            "body": "Need collab",
            "mentions": "neo,zeo",
        })
        post_id = r.json()["id"]

        r2 = await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "neo",
            "content": "@zeo can you help with this?",
            "mentions": "zeo",
        })
        assert r2.status_code == 201
        assert r2.json()["mentions"] == "zeo"

    async def test_reply_to_nonexistent_collab(self, client: AsyncClient):
        r = await client.post("/api/collab/99999/replies", json={
            "author": "neo",
            "content": "Ghost reply",
        })
        assert r.status_code == 404

    async def test_collab_replies_appear_in_post(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Replies in post test",
            "body": "Check if replies show up",
            "mentions": "vio",
        })
        post_id = r.json()["id"]

        await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "vio",
            "content": "Acknowledged, working on it.",
        })

        r2 = await client.get(f"/api/collab/{post_id}")
        assert r2.status_code == 200
        assert len(r2.json()["replies"]) == 1
        assert r2.json()["replies"][0]["author"] == "vio"

    async def test_human_can_reply_to_collab(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "neo",
            "subject": "Human reply test",
            "body": "Can the human help?",
            "mentions": "vio",
        })
        post_id = r.json()["id"]

        r2 = await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "human",
            "content": "Yes, I can help with this.",
        })
        assert r2.status_code == 201
        assert r2.json()["author"] == "human"


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class TestNotifications:
    async def test_collab_mention_creates_notification(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Notif test",
            "body": "Need input from Vio.",
            "mentions": "vio",
        })
        r = await client.get("/api/notifications", params={"agent_id": "vio", "unread": True})
        assert r.status_code == 200
        notifs = r.json()
        assert any(n["source_type"] == "collab" and n["author"] == "alfred" for n in notifs)

    async def test_chitchat_mention_creates_notification(self, client: AsyncClient):
        await client.post("/api/chitchat", json={
            "author": "neo",
            "content": "Hey @zeo check this out!",
            "mentions": "zeo",
        })
        r = await client.get("/api/notifications", params={"agent_id": "zeo", "unread": True})
        assert r.status_code == 200
        notifs = r.json()
        assert any(n["source_type"] == "chitchat" and n["author"] == "neo" for n in notifs)

    async def test_self_mention_does_not_notify(self, client: AsyncClient):
        await client.post("/api/chitchat", json={
            "author": "vio",
            "content": "Talking about myself @vio",
            "mentions": "vio",
        })
        r = await client.get("/api/notifications", params={"agent_id": "vio", "unread": True})
        notifs = r.json()
        self_notifs = [n for n in notifs if n["author"] == "vio" and n["agent_id"] == "vio"]
        assert len(self_notifs) == 0

    async def test_notification_count_endpoint(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Count test",
            "body": "Counting notifications.",
            "mentions": "neo",
        })
        r = await client.get("/api/notifications/count")
        assert r.status_code == 200
        counts = r.json()
        neo_count = next((c for c in counts if c["agent_id"] == "neo"), None)
        assert neo_count is not None
        assert neo_count["unread"] >= 1

    async def test_mark_notification_as_read(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "vio",
            "subject": "Read test",
            "body": "Please review.",
            "mentions": "zeo",
        })
        r = await client.get("/api/notifications", params={"agent_id": "zeo", "unread": True})
        notifs = r.json()
        assert len(notifs) > 0
        notif_id = notifs[0]["id"]

        r2 = await client.patch(f"/api/notifications/{notif_id}/read")
        assert r2.status_code == 200
        assert r2.json()["is_read"] == 1

    async def test_mark_all_read(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Bulk read test 1",
            "body": "First.",
            "mentions": "seo",
        })
        await client.post("/api/collab", json={
            "author": "neo",
            "subject": "Bulk read test 2",
            "body": "Second.",
            "mentions": "seo",
        })
        r = await client.patch("/api/notifications/read-all", params={"agent_id": "seo"})
        assert r.status_code == 200

        r2 = await client.get("/api/notifications", params={"agent_id": "seo", "unread": True})
        assert len(r2.json()) == 0

    async def test_mark_nonexistent_notification(self, client: AsyncClient):
        r = await client.patch("/api/notifications/99999/read")
        assert r.status_code == 404

    async def test_multi_mention_creates_multiple_notifications(self, client: AsyncClient):
        await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Multi mention",
            "body": "Need both of you.",
            "mentions": "vio,neo",
        })
        r_vio = await client.get("/api/notifications", params={"agent_id": "vio"})
        r_neo = await client.get("/api/notifications", params={"agent_id": "neo"})
        vio_has = any(n["source_type"] == "collab" and "Multi mention" in n.get("preview", "") for n in r_vio.json())
        neo_has = any(n["source_type"] == "collab" and "Multi mention" in n.get("preview", "") for n in r_neo.json())
        assert vio_has
        assert neo_has

    async def test_collab_reply_mention_creates_notification(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "neo",
            "subject": "Reply notif test",
            "body": "Initial post.",
            "mentions": "vio",
        })
        post_id = r.json()["id"]

        await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "vio",
            "content": "@zeo can you weigh in?",
            "mentions": "zeo",
        })
        r2 = await client.get("/api/notifications", params={"agent_id": "zeo"})
        assert any(n["source_type"] == "collab_reply" for n in r2.json())

    async def test_notifications_view_loads(self, client: AsyncClient):
        r = await client.get("/notifications")
        assert r.status_code == 200

    async def test_notifications_view_agent_filter(self, client: AsyncClient):
        r = await client.get("/notifications", params={"agent_id": "vio"})
        assert r.status_code == 200

    async def test_notification_guide_exists(self, client: AsyncClient):
        r = await client.get("/guides/notifications")
        assert r.status_code == 200

    async def test_chitchat_reply_notifies_post_author(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "vio",
            "content": "Working on the new dashboard!",
        })
        post_id = r.json()["id"]

        await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "neo",
            "content": "Looks great, nice work!",
        })
        r2 = await client.get("/api/notifications", params={"agent_id": "vio"})
        assert any(
            n["source_type"] == "chitchat_reply" and n["author"] == "neo"
            for n in r2.json()
        )

    async def test_collab_reply_notifies_post_author(self, client: AsyncClient):
        r = await client.post("/api/collab", json={
            "author": "alfred",
            "subject": "Author notif test",
            "body": "Need help with deployment.",
            "mentions": "neo",
        })
        post_id = r.json()["id"]

        await client.post(f"/api/collab/{post_id}/replies", json={
            "author": "neo",
            "content": "On it, will deploy shortly.",
        })
        r2 = await client.get("/api/notifications", params={"agent_id": "alfred"})
        assert any(
            n["source_type"] == "collab_reply" and n["author"] == "neo"
            for n in r2.json()
        )

    async def test_self_reply_does_not_notify_author(self, client: AsyncClient):
        r = await client.post("/api/chitchat", json={
            "author": "zeo",
            "content": "Thinking out loud...",
        })
        post_id = r.json()["id"]

        await client.post(f"/api/chitchat/{post_id}/replies", json={
            "author": "zeo",
            "content": "Actually, never mind.",
        })
        r2 = await client.get("/api/notifications", params={"agent_id": "zeo"})
        self_reply_notifs = [
            n for n in r2.json()
            if n["source_type"] == "chitchat_reply"
            and n["author"] == "zeo"
            and n["agent_id"] == "zeo"
        ]
        assert len(self_reply_notifs) == 0
