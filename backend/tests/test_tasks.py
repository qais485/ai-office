import pytest
from uuid import uuid4

from app.models.task import Task, TaskStatus, TaskPriority, TaskType
from app.services.task_service import TaskService


# ---------------------------------------------------------------------------
# TestTaskCRUD
# ---------------------------------------------------------------------------

class TestTaskCRUD:
    def test_create_task(self, client, ceo_headers, sample_agent):
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "New Task",
                "description": "A brand new task",
                "agent_id": str(sample_agent.id),
                "task_type": "general",
                "priority": "medium",
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "New Task"
        assert data["description"] == "A brand new task"
        assert data["agent_id"] == str(sample_agent.id)
        assert data["status"] == "pending"
        assert data["priority"] == "medium"
        assert "id" in data

    def test_create_task_minimal_fields(self, client, ceo_headers, sample_agent):
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Minimal Task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Minimal Task"
        assert data["priority"] == "medium"
        assert data["task_type"] == "general"

    def test_list_tasks(self, client, ceo_headers, sample_task):
        resp = client.get("/api/v1/tasks/", headers=ceo_headers)
        assert resp.status_code == 200
        tasks = resp.json()
        assert isinstance(tasks, list)
        assert len(tasks) >= 1
        ids = [t["id"] for t in tasks]
        assert str(sample_task.id) in ids

    def test_get_task_by_id(self, client, ceo_headers, sample_task):
        resp = client.get(f"/api/v1/tasks/{sample_task.id}", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_task.id)
        assert data["title"] == "Test Task"

    def test_get_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.get(f"/api/v1/tasks/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_update_task(self, client, ceo_headers, sample_task):
        resp = client.put(
            f"/api/v1/tasks/{sample_task.id}",
            json={
                "title": "Updated Task",
                "priority": "high",
                "status": "running",
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Task"
        assert data["priority"] == "high"
        assert data["status"] == "running"

    def test_update_task_partial(self, client, ceo_headers, sample_task):
        resp = client.put(
            f"/api/v1/tasks/{sample_task.id}",
            json={"title": "Partially Updated"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Partially Updated"
        assert data["priority"] == "medium"

    def test_update_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.put(
            f"/api/v1/tasks/{fake_id}",
            json={"title": "Ghost Task"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_delete_task(self, client, ceo_headers, sample_task):
        resp = client.delete(f"/api/v1/tasks/{sample_task.id}", headers=ceo_headers)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Task deleted"
        get_resp = client.get(f"/api/v1/tasks/{sample_task.id}", headers=ceo_headers)
        assert get_resp.status_code == 404

    def test_delete_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.delete(f"/api/v1/tasks/{fake_id}", headers=ceo_headers)
        assert resp.status_code == 404

    def test_create_multiple_tasks(self, client, ceo_headers, sample_agent):
        for i in range(3):
            resp = client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
            assert resp.status_code == 200

        list_resp = client.get("/api/v1/tasks/", headers=ceo_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 3

    def test_unauthenticated_cannot_create_task(self, client, sample_agent):
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Unauthorized Task",
                "agent_id": str(sample_agent.id),
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# TestTaskStatusFlow
# ---------------------------------------------------------------------------

class TestTaskStatusFlow:
    def test_pending_to_running(self, client, ceo_headers, sample_task):
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["started_at"] is not None

    def test_running_to_completed(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Task finished successfully"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "Task finished successfully"
        assert data["completed_at"] is not None

    def test_pending_to_running_to_completed_full_flow(
        self, client, ceo_headers, sample_task
    ):
        resp = client.get(f"/api/v1/tasks/{sample_task.id}", headers=ceo_headers)
        assert resp.json()["status"] == "pending"

        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        assert resp.json()["status"] == "running"

        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Done"},
            headers=ceo_headers,
        )
        assert resp.json()["status"] == "completed"

    def test_pending_to_running_to_failed(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/fail",
            params={"error_message": "Something went wrong"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error_message"] == "Something went wrong"

    def test_pending_to_cancelled(self, client, ceo_headers, sample_task):
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/cancel",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    def test_running_to_cancelled(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/cancel",
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cannot_start_completed_task(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Done"},
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_cannot_complete_pending_task(self, client, ceo_headers, sample_task):
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Done"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_cannot_start_already_running_task(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_fail_task_from_pending(self, client, ceo_headers, sample_task):
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/fail",
            params={"error_message": "Failed before starting"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_cannot_complete_failed_task(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/fail",
            params={"error_message": "Oops"},
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Actually done"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_start_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/tasks/{fake_id}/start",
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_complete_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/tasks/{fake_id}/complete",
            params={"result": "Done"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_fail_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/tasks/{fake_id}/fail",
            params={"error_message": "Not found"},
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_cancel_task_not_found(self, client, ceo_headers):
        fake_id = uuid4()
        resp = client.post(
            f"/api/v1/tasks/{fake_id}/cancel",
            headers=ceo_headers,
        )
        assert resp.status_code == 404

    def test_cancel_completed_task_fails(self, client, ceo_headers, sample_task):
        client.post(
            f"/api/v1/tasks/{sample_task.id}/start",
            headers=ceo_headers,
        )
        client.post(
            f"/api/v1/tasks/{sample_task.id}/complete",
            params={"result": "Done"},
            headers=ceo_headers,
        )
        resp = client.post(
            f"/api/v1/tasks/{sample_task.id}/cancel",
            headers=ceo_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TestTaskPriority
# ---------------------------------------------------------------------------

class TestTaskPriority:
    def _create_task_with_priority(self, client, ceo_headers, sample_agent, priority):
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": f"Task with {priority} priority",
                "agent_id": str(sample_agent.id),
                "priority": priority,
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        return resp.json()

    def test_low_priority(self, client, ceo_headers, sample_agent):
        data = self._create_task_with_priority(
            client, ceo_headers, sample_agent, "low"
        )
        assert data["priority"] == "low"

    def test_medium_priority(self, client, ceo_headers, sample_agent):
        data = self._create_task_with_priority(
            client, ceo_headers, sample_agent, "medium"
        )
        assert data["priority"] == "medium"

    def test_high_priority(self, client, ceo_headers, sample_agent):
        data = self._create_task_with_priority(
            client, ceo_headers, sample_agent, "high"
        )
        assert data["priority"] == "high"

    def test_urgent_priority(self, client, ceo_headers, sample_agent):
        data = self._create_task_with_priority(
            client, ceo_headers, sample_agent, "urgent"
        )
        assert data["priority"] == "urgent"

    def test_default_priority_is_medium(self, client, ceo_headers, sample_agent):
        resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Default priority task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "medium"

    def test_update_priority(self, client, ceo_headers, sample_task):
        resp = client.put(
            f"/api/v1/tasks/{sample_task.id}",
            json={"priority": "urgent"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "urgent"

    def test_all_priorities_listed(self, client, ceo_headers, sample_agent):
        priorities = ["low", "medium", "high", "urgent"]
        task_ids = []
        for p in priorities:
            resp = client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Priority {p}",
                    "agent_id": str(sample_agent.id),
                    "priority": p,
                },
                headers=ceo_headers,
            )
            assert resp.status_code == 200
            task_ids.append(resp.json()["id"])

        for tid, p in zip(task_ids, priorities):
            resp = client.get(f"/api/v1/tasks/{tid}", headers=ceo_headers)
            assert resp.status_code == 200
            assert resp.json()["priority"] == p


# ---------------------------------------------------------------------------
# TestTaskStats
# ---------------------------------------------------------------------------

class TestTaskStats:
    def test_stats_returns_expected_fields(self, client, ceo_headers):
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "pending" in data
        assert "running" in data
        assert "completed" in data
        assert "failed" in data
        assert "cancelled" in data
        assert "waiting_approval" in data

    def test_stats_empty_database(self, client, ceo_headers):
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["pending"] == 0
        assert data["running"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["cancelled"] == 0
        assert data["waiting_approval"] == 0

    def test_stats_with_pending_tasks(self, client, ceo_headers, sample_agent):
        for i in range(3):
            client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Pending Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert data["pending"] >= 3

    def test_stats_with_completed_tasks(self, client, ceo_headers, sample_agent):
        for i in range(2):
            create_resp = client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Complete Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
            task_id = create_resp.json()["id"]
            client.post(
                f"/api/v1/tasks/{task_id}/start",
                headers=ceo_headers,
            )
            client.post(
                f"/api/v1/tasks/{task_id}/complete",
                params={"result": f"Done {i}"},
                headers=ceo_headers,
            )
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed"] >= 2

    def test_stats_with_failed_tasks(self, client, ceo_headers, sample_agent):
        create_resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Failing Task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )
        task_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/tasks/{task_id}/start",
            headers=ceo_headers,
        )
        client.post(
            f"/api/v1/tasks/{task_id}/fail",
            params={"error_message": "Kaboom"},
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed"] >= 1

    def test_stats_with_cancelled_tasks(self, client, ceo_headers, sample_agent):
        create_resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Cancelled Task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )
        task_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/tasks/{task_id}/cancel",
            headers=ceo_headers,
        )
        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] >= 1

    def test_stats_total_matches_sum_of_statuses(
        self, client, ceo_headers, sample_agent
    ):
        for i in range(5):
            create_resp = client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Stat Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
            task_id = create_resp.json()["id"]
            if i < 2:
                client.post(
                    f"/api/v1/tasks/{task_id}/start",
                    headers=ceo_headers,
                )
                client.post(
                    f"/api/v1/tasks/{task_id}/complete",
                    params={"result": "Done"},
                    headers=ceo_headers,
                )
            elif i == 2:
                client.post(
                    f"/api/v1/tasks/{task_id}/start",
                    headers=ceo_headers,
                )
                client.post(
                    f"/api/v1/tasks/{task_id}/fail",
                    params={"error_message": "Fail"},
                    headers=ceo_headers,
                )
            elif i == 3:
                client.post(
                    f"/api/v1/tasks/{task_id}/cancel",
                    headers=ceo_headers,
                )

        resp = client.get("/api/v1/tasks/stats/summary", headers=ceo_headers)
        data = resp.json()
        status_sum = (
            data["pending"]
            + data["running"]
            + data["completed"]
            + data["failed"]
            + data["cancelled"]
            + data["waiting_approval"]
        )
        assert data["total"] == status_sum

    def test_stats_filter_by_agent(self, client, ceo_headers, sample_agent, api_db):
        from app.models.agent import AIAgent, AgentStatus, LifecycleStatus

        other_agent = AIAgent(
            id=uuid4(),
            name="Other Agent",
            role="writer",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
        )
        api_db.add(other_agent)
        api_db.flush()

        for i in range(2):
            client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Agent1 Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Agent2 Task",
                "agent_id": str(other_agent.id),
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/stats/summary",
            params={"agent_id": str(sample_agent.id)},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2


# ---------------------------------------------------------------------------
# TestTaskFiltering
# ---------------------------------------------------------------------------

class TestTaskFiltering:
    def test_filter_by_agent_id(self, client, ceo_headers, sample_agent, api_db):
        from app.models.agent import AIAgent, AgentStatus, LifecycleStatus

        other_agent = AIAgent(
            id=uuid4(),
            name="Filter Agent",
            role="analyst",
            status=AgentStatus.INACTIVE,
            lifecycle_status=LifecycleStatus.DRAFT,
        )
        api_db.add(other_agent)
        api_db.flush()

        for i in range(2):
            client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Agent Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Other Agent Task",
                "agent_id": str(other_agent.id),
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/",
            params={"agent_id": str(sample_agent.id)},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        tasks = resp.json()
        agent_ids = {t["agent_id"] for t in tasks}
        assert all(aid == str(sample_agent.id) for aid in agent_ids)

    def test_filter_by_status(self, client, ceo_headers, sample_agent):
        create_resp = client.post(
            "/api/v1/tasks/",
            json={
                "title": "Running Filter Task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )
        running_id = create_resp.json()["id"]
        client.post(
            f"/api/v1/tasks/{running_id}/start",
            headers=ceo_headers,
        )

        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Pending Filter Task",
                "agent_id": str(sample_agent.id),
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/",
            params={"status": "running"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["status"] == "running" for t in tasks)
        running_ids = [t["id"] for t in tasks]
        assert running_id in running_ids

    def test_filter_by_priority(self, client, ceo_headers, sample_agent):
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Urgent Filter Task",
                "agent_id": str(sample_agent.id),
                "priority": "urgent",
            },
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Low Filter Task",
                "agent_id": str(sample_agent.id),
                "priority": "low",
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/",
            params={"priority": "urgent"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["priority"] == "urgent" for t in tasks)

    def test_filter_by_task_type(self, client, ceo_headers, sample_agent):
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "General Type Task",
                "agent_id": str(sample_agent.id),
                "task_type": "general",
            },
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Tool Type Task",
                "agent_id": str(sample_agent.id),
                "task_type": "tool_execution",
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/",
            params={"task_type": "tool_execution"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["task_type"] == "tool_execution" for t in tasks)

    def test_combined_filters(self, client, ceo_headers, sample_agent):
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "High Urgent",
                "agent_id": str(sample_agent.id),
                "priority": "high",
            },
            headers=ceo_headers,
        )
        client.post(
            "/api/v1/tasks/",
            json={
                "title": "Low Urgent",
                "agent_id": str(sample_agent.id),
                "priority": "low",
            },
            headers=ceo_headers,
        )

        resp = client.get(
            "/api/v1/tasks/",
            params={"priority": "high"},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        tasks = resp.json()
        assert all(t["priority"] == "high" for t in tasks)

    def test_filter_limit(self, client, ceo_headers, sample_agent):
        for i in range(5):
            client.post(
                "/api/v1/tasks/",
                json={
                    "title": f"Limit Task {i}",
                    "agent_id": str(sample_agent.id),
                },
                headers=ceo_headers,
            )
        resp = client.get(
            "/api/v1/tasks/",
            params={"limit": 2},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    def test_filter_no_results(self, client, ceo_headers):
        fake_agent_id = uuid4()
        resp = client.get(
            "/api/v1/tasks/",
            params={"agent_id": str(fake_agent_id)},
            headers=ceo_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# TestTaskService (Neon DB)
# ---------------------------------------------------------------------------

class TestTaskService:
    def test_service_create_task(self, db, neon_agent):
        service = TaskService(db)
        from app.schemas.task import TaskCreate

        task_data = TaskCreate(
            title="Service Task",
            agent_id=neon_agent.id,
            priority="high",
        )
        task = service.create_task(task_data)
        assert task.title == "Service Task"
        assert task.priority.value == "high"
        assert task.status.value == "pending"

    def test_service_get_tasks(self, db, neon_agent):
        service = TaskService(db)
        from app.schemas.task import TaskCreate

        for i in range(3):
            service.create_task(
                TaskCreate(title=f"Service Task {i}", agent_id=neon_agent.id)
            )
        tasks = service.get_tasks()
        assert len(tasks) >= 3

    def test_service_get_tasks_by_agent(self, db, neon_agent):
        service = TaskService(db)
        from app.schemas.task import TaskCreate

        service.create_task(
            TaskCreate(title="Agent Task", agent_id=neon_agent.id)
        )
        tasks = service.get_tasks(agent_id=neon_agent.id)
        assert all(t.agent_id == neon_agent.id for t in tasks)

    def test_service_start_task(self, db, neon_task):
        service = TaskService(db)
        task = service.start_task(neon_task.id)
        assert task.status.value == "running"
        assert task.started_at is not None

    def test_service_complete_task(self, db, neon_task):
        service = TaskService(db)
        service.start_task(neon_task.id)
        task = service.complete_task(neon_task.id, result="Finished")
        assert task.status.value == "completed"
        assert task.result == "Finished"

    def test_service_fail_task(self, db, neon_task):
        service = TaskService(db)
        service.start_task(neon_task.id)
        task = service.fail_task(neon_task.id, error_message="Error occurred")
        assert task.status.value == "failed"
        assert task.error_message == "Error occurred"

    def test_service_cancel_task(self, db, neon_task):
        service = TaskService(db)
        task = service.cancel_task(neon_task.id)
        assert task.status.value == "cancelled"

    def test_service_get_task_stats(self, db, neon_agent):
        service = TaskService(db)
        from app.schemas.task import TaskCreate

        service.create_task(
            TaskCreate(title="Stats Task", agent_id=neon_agent.id)
        )
        stats = service.get_task_stats(agent_id=neon_agent.id)
        assert "total" in stats
        assert "pending" in stats
        assert "running" in stats
        assert "completed" in stats
        assert "failed" in stats
        assert "cancelled" in stats
        assert "waiting_approval" in stats
        assert stats["total"] >= 1

    def test_service_delete_task(self, db, neon_task):
        service = TaskService(db)
        result = service.delete_task(neon_task.id)
        assert result is True
        assert service.get_task(neon_task.id) is None

    def test_service_update_task(self, db, neon_task):
        service = TaskService(db)
        from app.schemas.task import TaskUpdate

        updated = service.update_task(neon_task.id, TaskUpdate(title="Updated Neon"))
        assert updated.title == "Updated Neon"
