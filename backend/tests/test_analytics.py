"""Tests for Analytics: agent performance, company analytics, rankings."""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.services.analytics_service import AnalyticsService


class TestAgentPerformance:
    """Returns performance metrics for an agent."""

    def test_get_agent_performance_via_api(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "agent_id" in data
        assert data["agent_id"] == str(agent_id)

    def test_performance_contains_required_fields(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert "tasks_completed" in data
        assert "tasks_failed" in data
        assert "success_rate" in data
        assert "avg_duration_seconds" in data
        assert "activities_count" in data
        assert "approvals_pending" in data
        assert "period_days" in data

    def test_performance_with_custom_days(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}?days=7")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7

    def test_performance_days_min_validation(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}?days=0")
        assert response.status_code == 422

    def test_performance_days_max_validation(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}?days=366")
        assert response.status_code == 422

    def test_performance_returns_zero_for_no_tasks(self, api_db, sample_agent, ceo_headers, client):
        agent_id = sample_agent.id
        response = client.get(f"/api/v1/analytics/agent/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["tasks_completed"] == 0
        assert data["tasks_failed"] == 0
        assert data["success_rate"] == 0

    def test_performance_service_method(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_performance(sample_agent.id, days=30)
        assert isinstance(result, dict)
        assert "agent_id" in result
        assert "tasks_completed" in result
        assert "success_rate" in result

    def test_performance_service_with_zero_tasks(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_performance(sample_agent.id, days=30)
        assert result["tasks_completed"] == 0
        assert result["tasks_failed"] == 0
        assert result["success_rate"] == 0
        assert result["activities_count"] == 0

    def test_performance_includes_pending_approvals(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_performance(sample_agent.id, days=30)
        assert "approvals_pending" in result
        assert isinstance(result["approvals_pending"], int)


class TestCompanyAnalytics:
    """Returns company-wide analytics."""

    def test_get_company_analytics_via_api(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_company_analytics_contains_required_fields(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company")
        assert response.status_code == 200
        data = response.json()
        assert "period_days" in data
        assert "total_agents" in data
        assert "total_tasks_completed" in data
        assert "total_tasks_failed" in data
        assert "success_rate" in data
        assert "total_activities" in data
        assert "pending_approvals" in data

    def test_company_analytics_with_custom_days(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company?days=7")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7

    def test_company_analytics_days_min_validation(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company?days=0")
        assert response.status_code == 422

    def test_company_analytics_days_max_validation(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company?days=366")
        assert response.status_code == 422

    def test_company_analytics_service_method(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_company_analytics(days=30)
        assert isinstance(result, dict)
        assert "total_agents" in result
        assert "success_rate" in result

    def test_company_analytics_zero_tasks(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_company_analytics(days=30)
        assert result["total_tasks_completed"] == 0
        assert result["total_tasks_failed"] == 0
        assert result["success_rate"] == 0

    def test_company_analytics_default_days(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/company")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30

    def test_company_analytics_returns_numeric_rates(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_company_analytics(days=30)
        assert isinstance(result["success_rate"], float)


class TestAgentRanking:
    """Returns agents ranked by performance."""

    def test_get_agent_ranking_via_api(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_ranking_items_contain_required_fields(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            item = data[0]
            assert "agent_id" in item
            assert "agent_name" in item
            assert "tasks_completed" in item
            assert "success_rate" in item

    def test_ranking_with_custom_days(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking?days=7")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_ranking_days_min_validation(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking?days=0")
        assert response.status_code == 422

    def test_ranking_days_max_validation(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking?days=366")
        assert response.status_code == 422

    def test_ranking_sorted_by_tasks_completed(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_ranking(days=30)
        assert isinstance(result, list)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i]["tasks_completed"] >= result[i + 1]["tasks_completed"]

    def test_ranking_service_method(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_ranking(days=30)
        assert isinstance(result, list)

    def test_ranking_empty_when_no_active_agents(self, api_db):
        service = AnalyticsService(api_db)
        result = service.get_agent_ranking(days=30)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_ranking_includes_agent_name(self, api_db, sample_agent):
        service = AnalyticsService(api_db)
        result = service.get_agent_ranking(days=30)
        if len(result) > 0:
            assert "agent_name" in result[0]
            assert isinstance(result[0]["agent_name"], str)

    def test_ranking_default_days(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/ranking")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_daily_stats_endpoint(self, api_db, sample_agent, ceo_headers, client):
        response = client.get("/api/v1/analytics/daily")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            item = data[0]
            assert "date" in item
            assert "tasks_completed" in item
            assert "tasks_failed" in item
            assert "activities_count" in item
