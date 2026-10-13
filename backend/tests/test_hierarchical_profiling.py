"""Unit and regression tests for Hierarchical Agent Proficiency Profiling.

Covers:
1. Micro-level profiling for all 7 actual pipeline agents:
   - System Orchestrator
   - Requirement Analyst Agent
   - Codebase Analyst & Planner Agent
   - Coding Agent
   - Test Runner Agent
   - Debugging & Recovery Agent
   - Independent Code Reviewer & Verifier Agent
2. Macro-level end-to-end system profile
3. Direct observed outcome percentages and insufficient-evidence handling
4. Accurate failure attribution (syntax, logic, harness, planner, debugger exhaustion)
5. Accurate recovery attribution (resolved vs exhausted)
6. Zero fabrication and insufficient evidence handling
7. REST API endpoints integration
"""
import json
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.hierarchical_proficiency_service import (
    HierarchicalProficiencyService,
    AGENT_REGISTRY,
    ALL_AGENT_IDS,
)


@pytest.fixture
def tmp_db_service(tmp_path):
    """Provide a fresh SQLite database and DB service for test isolation."""
    from app.services import db as db_module
    db_file = str(tmp_path / "test_hierarchical.db")
    original_path = db_module.db_service.db_path
    db_module.db_service.db_path = db_file
    db_module.db_service._init_db()

    svc = HierarchicalProficiencyService()
    svc.db_path = db_file
    svc._apply_migrations()

    yield svc, db_file

    db_module.db_service.db_path = original_path


class TestHierarchicalAgentStructure:
    """Verify all 7 agents and system profile are tracked in the hierarchy."""

    def test_registry_contains_all_seven_actual_agents(self):
        expected_agents = {
            "orchestrator",
            "requirement_analyst",
            "planner",
            "coder",
            "test_runner",
            "debugger",
            "verifier"
        }
        assert set(AGENT_REGISTRY.keys()) == expected_agents
        assert len(ALL_AGENT_IDS) == 7

    def test_empty_database_returns_all_seven_agents_with_insufficient_evidence(self, tmp_db_service):
        svc, _ = tmp_db_service
        result = svc.get_hierarchical_profiles()

        assert "agent_profiles" in result
        assert "system_profile" in result
        assert "attribution_matrix" in result

        # Must contain all 7 agents
        assert len(result["agent_profiles"]) == 7
        for agent_id in ALL_AGENT_IDS:
            assert agent_id in result["agent_profiles"]
            prof = result["agent_profiles"][agent_id]
            assert prof["agent_id"] == agent_id
            assert prof["evidence_status"] == "insufficient_evidence"
            assert prof["sample_size"] == 0
            assert prof["primary_metric"]["observed_rate"] is None
            assert "posterior_mean" not in prof["primary_metric"]
            assert prof["measurement_basis"]

        # System profile must also show insufficient evidence
        sys_prof = result["system_profile"]
        assert sys_prof["evidence_status"] == "insufficient_evidence"
        assert sys_prof["total_runs_analyzed"] == 0
        assert sys_prof["verified_success_rate"]["sample_size"] == 0


class TestFailureAndRecoveryAttribution:
    """Verify deterministic root-cause failure and recovery attribution."""

    def test_syntax_failure_attribution(self, tmp_db_service):
        svc, db_file = tmp_db_service
        conn = sqlite3.connect(db_file)
        # Create a run where code change has AST syntax error
        run_id = "run_syntax_err"
        conn.execute("INSERT INTO runs (run_id, task_id, title, prompt, repo_path, current_stage, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (run_id, "t1", "Syntax Test", "prompt", "repo", "completed", "completed", "now", "now"))
        conn.execute("INSERT INTO goal_models (run_id, data_json, created_at, updated_at) VALUES (?,?,?,?)",
                     (run_id, json.dumps({"sub_goals": ["g1"], "success_criteria": ["c1"]}), "now", "now"))
        conn.execute("INSERT INTO plans (run_id, data_json, created_at) VALUES (?,?,?)",
                     (run_id, json.dumps({"steps": ["s1"], "planned_files": [{"path": "a.py"}]}), "now"))
        # Code change with ast_valid = 0
        conn.execute("INSERT INTO code_changes (id, run_id, file_path, action, new_content, diff_patch, lines_added, lines_removed, ast_valid, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("c1", run_id, "a.py", "modify", "invalid syntax code", "+error", 1, 0, 0, "now"))
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr1", run_id, 1, 1, 0, 1, 1, "FAILED", 1.2, "{}", "now"))
        conn.commit()

        res = svc.record_run_proficiencies(run_id, model_name="qwen2.5-coder:7b")
        assert res["attribution"]["primary_root_cause"] == "coder_syntax_failure"
        assert res["attribution"]["coder_attribution"] == "root_cause_syntax"

    def test_logic_failure_attribution(self, tmp_db_service):
        svc, db_file = tmp_db_service
        conn = sqlite3.connect(db_file)
        run_id = "run_logic_err"
        conn.execute("INSERT INTO runs (run_id, task_id, title, prompt, repo_path, current_stage, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (run_id, "t2", "Logic Test", "prompt", "repo", "completed", "completed", "now", "now"))
        conn.execute("INSERT INTO goal_models (run_id, data_json, created_at, updated_at) VALUES (?,?,?,?)",
                     (run_id, json.dumps({"sub_goals": ["g1"], "success_criteria": ["c1"]}), "now", "now"))
        conn.execute("INSERT INTO plans (run_id, data_json, created_at) VALUES (?,?,?)",
                     (run_id, json.dumps({"steps": ["s1"], "planned_files": [{"path": "b.py"}]}), "now"))
        # ast_valid = 1
        conn.execute("INSERT INTO code_changes (id, run_id, file_path, action, new_content, diff_patch, lines_added, lines_removed, ast_valid, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("c2", run_id, "b.py", "modify", "def add(a, b): return a - b", "+code", 1, 0, 1, "now"))
        # Initial test fails
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr2", run_id, 1, 2, 0, 2, 1, "FAILED", 1.5, "{}", "now"))
        conn.commit()

        res = svc.record_run_proficiencies(run_id, model_name="qwen2.5-coder:7b")
        assert res["attribution"]["primary_root_cause"] == "coder_logic_failure"
        assert res["attribution"]["coder_attribution"] == "root_cause_logic"

    def test_debugger_recovery_attribution_resolved(self, tmp_db_service):
        svc, db_file = tmp_db_service
        conn = sqlite3.connect(db_file)
        run_id = "run_recovery_pass"
        conn.execute("INSERT INTO runs (run_id, task_id, title, prompt, repo_path, current_stage, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (run_id, "t3", "Recovery Test", "prompt", "repo", "completed", "completed", "now", "now"))
        conn.execute("INSERT INTO goal_models (run_id, data_json, created_at, updated_at) VALUES (?,?,?,?)",
                     (run_id, json.dumps({"sub_goals": ["g1"], "success_criteria": ["c1"]}), "now", "now"))
        conn.execute("INSERT INTO plans (run_id, data_json, created_at) VALUES (?,?,?)",
                     (run_id, json.dumps({"steps": ["s1"], "planned_files": [{"path": "c.py"}]}), "now"))
        conn.execute("INSERT INTO code_changes (id, run_id, file_path, action, new_content, diff_patch, lines_added, lines_removed, ast_valid, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("c3", run_id, "c.py", "modify", "valid code", "+code", 1, 0, 1, "now"))
        # Test 1 failed, Test 2 passed
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr1", run_id, 1, 1, 0, 1, 1, "FAILED", 1.0, "{}", "now"))
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr2", run_id, 2, 1, 1, 0, 0, "PASSED", 1.0, "{}", "now"))
        # Recovery attempt marked resolved
        conn.execute("INSERT INTO recovery_attempts (id, run_id, attempt_number, failure_reason, diagnosis, root_cause_analysis, proposed_fix, resolved, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("ra1", run_id, 1, "assert error", "logic bug", "fix returned val", "patch", 1, "now"))
        conn.commit()

        res = svc.record_run_proficiencies(run_id, model_name="qwen2.5-coder:7b")
        assert res["attribution"]["recovery_outcome"] == "debugger_recovered"

    def test_debugger_exhaustion_attribution(self, tmp_db_service):
        svc, db_file = tmp_db_service
        conn = sqlite3.connect(db_file)
        run_id = "run_recovery_exhausted"
        conn.execute("INSERT INTO runs (run_id, task_id, title, prompt, repo_path, current_stage, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (run_id, "t4", "Exhaustion Test", "prompt", "repo", "completed", "completed", "now", "now"))
        conn.execute("INSERT INTO goal_models (run_id, data_json, created_at, updated_at) VALUES (?,?,?,?)",
                     (run_id, json.dumps({"sub_goals": ["g1"], "success_criteria": ["c1"]}), "now", "now"))
        conn.execute("INSERT INTO plans (run_id, data_json, created_at) VALUES (?,?,?)",
                     (run_id, json.dumps({"steps": ["s1"], "planned_files": [{"path": "d.py"}]}), "now"))
        conn.execute("INSERT INTO code_changes (id, run_id, file_path, action, new_content, diff_patch, lines_added, lines_removed, ast_valid, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("c4", run_id, "d.py", "modify", "valid code", "+code", 1, 0, 1, "now"))
        # Both attempts failed
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr1", run_id, 1, 1, 0, 1, 1, "FAILED", 1.0, "{}", "now"))
        conn.execute("INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, exit_code, status, duration_seconds, data_json, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     ("tr2", run_id, 2, 1, 0, 1, 1, "FAILED", 1.0, "{}", "now"))
        conn.execute("INSERT INTO recovery_attempts (id, run_id, attempt_number, failure_reason, diagnosis, root_cause_analysis, proposed_fix, resolved, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("ra1", run_id, 1, "assert error", "logic bug", "fix returned val", "patch", 0, "now"))
        conn.commit()

        res = svc.record_run_proficiencies(run_id, model_name="qwen2.5-coder:7b")
        assert res["attribution"]["recovery_outcome"] == "unresolved_failure"
        assert "debugger_exhaustion" in res["attribution"]["all_causes"]


class TestDirectObservedOutcomes:
    """Verify profile percentages use only observed successes and failures."""

    def test_hierarchical_rate_is_raw_observed_ratio(self, tmp_db_service):
        svc, db_file = tmp_db_service
        conn = sqlite3.connect(db_file)

        # Insert 3 successful planner observations and 1 failure
        for i in range(3):
            conn.execute(
                "INSERT INTO agent_proficiency_observations "
                "(obs_id, run_id, agent_id, model_name, metric_name, successes, failures, created_at) "
                "VALUES (?, ?, 'planner', 'qwen2.5-coder:7b', 'plan_feasibility_rate', 1, 0, 'now')",
                (f"obs_p_{i}", f"run_p_{i}")
            )
        conn.execute(
            "INSERT INTO agent_proficiency_observations "
            "(obs_id, run_id, agent_id, model_name, metric_name, successes, failures, created_at) "
            "VALUES (?, ?, 'planner', 'qwen2.5-coder:7b', 'plan_feasibility_rate', 0, 1, 'now')",
            ("obs_p_fail", "run_p_fail")
        )
        conn.commit()

        profiles = svc.get_hierarchical_profiles(model_name="qwen2.5-coder:7b")
        planner_prof = profiles["agent_profiles"]["planner"]

        assert planner_prof["sample_size"] == 4
        assert planner_prof["evidence_status"] == "measured"
        pm = planner_prof["primary_metric"]
        assert pm["successes"] == 3
        assert pm["failures"] == 1
        assert pm["sample_size"] == 4
        assert pm["observed_rate"] == 0.75
        assert "posterior_mean" not in pm


class TestHierarchicalAPIEndpoints:
    """Verify FastAPI route responses and contracts."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)

    def test_get_hierarchical_proficiency_returns_valid_structure(self):
        resp = self.client.get("/api/features/hierarchical-proficiency")
        assert resp.status_code == 200
        data = resp.json()

        assert "agent_profiles" in data
        assert "system_profile" in data
        assert "attribution_matrix" in data
        assert len(data["agent_profiles"]) == 7

        # Check all 7 agent keys
        for agent_id in ALL_AGENT_IDS:
            assert agent_id in data["agent_profiles"]
            agent_data = data["agent_profiles"][agent_id]
            assert "primary_metric" in agent_data
            assert "observed_rate" in agent_data["primary_metric"]
            assert "measurement_basis" in agent_data

    def test_get_hierarchical_proficiency_with_model_filter(self):
        resp = self.client.get("/api/features/hierarchical-proficiency?model_name=qwen2.5-coder:7b")
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "qwen2.5-coder:7b"

    def test_post_rebuild_hierarchical_proficiency(self):
        resp = self.client.post("/api/features/hierarchical-proficiency/rebuild")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "runs_synced" in data
