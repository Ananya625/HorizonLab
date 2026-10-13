"""Automated tests for the Evidence-Grounded Capability Profiling System.

Covers:
1. Beta-Binomial statistical calculations
2. Observation deduplication by stable obs_id
3. Recovery episode accounting (verified vs unverified)
4. Evidence status for missing data
5. SQLite persistence and reproducibility
6. Trajectory label propagation (no label leakage)
7. API response structure (FastAPI test client)
"""
import json
import math
import os
import sqlite3
import tempfile
import uuid
import pytest
from unittest.mock import patch, MagicMock


# ───────────────────────────────────────────────────────────────────────────
# 1. Beta-Binomial estimator
# ───────────────────────────────────────────────────────────────────────────

class TestBetaBinomialEstimator:
    """Tests for capability_estimator.compute_beta_binomial."""

    def setup_method(self):
        from app.services.capability_estimator import compute_beta_binomial
        self.compute = compute_beta_binomial

    def test_uniform_prior_zero_observations(self):
        est = self.compute("reliability", successes=0, failures=0)
        assert est.evidence_status == "insufficient_evidence"
        assert est.sample_size == 0
        assert est.observed_rate is None
        # Posterior mean under Beta(1,1) with 0 obs = 1/(1+1) = 0.5
        assert abs(est.posterior_mean - 0.5) < 1e-9

    def test_posterior_mean_formula(self):
        # s=3 f=1, alpha_prior=1, beta_prior=1
        # posterior_alpha=4, posterior_beta=2 → mean=4/6≈0.6667
        est = self.compute("reliability", successes=3, failures=1)
        assert abs(est.posterior_mean - (4 / 6)) < 1e-3

    def test_posterior_alpha_beta_values(self):
        est = self.compute("coding", successes=7, failures=2, alpha_prior=2.0, beta_prior=3.0)
        assert abs(est.posterior_alpha - 9.0) < 1e-9
        assert abs(est.posterior_beta - 5.0) < 1e-9

    def test_observed_rate_separate_from_posterior(self):
        est = self.compute("recovery", successes=2, failures=2)
        assert est.observed_rate == pytest.approx(0.5, abs=1e-3)
        # With Beta(1,1) prior: posterior_mean = (1+2)/(1+2+1+2) = 3/6 = 0.5
        assert est.posterior_mean == pytest.approx(0.5, abs=1e-3)

    def test_credible_interval_ordering(self):
        est = self.compute("reliability", successes=8, failures=2)
        assert est.credible_interval_lower is not None
        assert est.credible_interval_upper is not None
        assert est.credible_interval_lower < est.posterior_mean
        assert est.posterior_mean < est.credible_interval_upper

    def test_credible_interval_within_zero_one(self):
        est = self.compute("coding", successes=10, failures=0)
        assert 0.0 <= est.credible_interval_lower <= 1.0
        assert 0.0 <= est.credible_interval_upper <= 1.0

    def test_low_sample_note(self):
        est = self.compute("reliability", successes=1, failures=0)
        assert "Low sample" in est.note or "provisional" in est.note.lower()
        assert est.evidence_status == "estimated"

    def test_to_dict_keys(self):
        est = self.compute("reliability", successes=5, failures=2)
        d = est.to_dict()
        for key in [
            "capability", "successes", "failures", "sample_size",
            "alpha_prior", "beta_prior", "posterior_alpha", "posterior_beta",
            "observed_rate", "posterior_mean",
            "credible_interval_lower", "credible_interval_upper",
            "evidence_status", "note",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_do_not_apply_to_continuous(self):
        """Sanity: estimator should never be called for duration values."""
        from app.services.capability_estimator import ContinuousSummary
        s = ContinuousSummary(measurement="task_duration", unit="seconds", values=[30.0, 45.5, 22.1])
        d = s.to_dict()
        assert d["evidence_status"] == "measured"
        assert d["n"] == 3
        assert abs(d["mean"] - (30.0 + 45.5 + 22.1) / 3) < 1e-3

    def test_continuous_empty(self):
        from app.services.capability_estimator import ContinuousSummary
        s = ContinuousSummary(measurement="task_duration", unit="seconds", values=[])
        d = s.to_dict()
        assert d["evidence_status"] == "insufficient_evidence"
        assert d["mean"] is None


# ───────────────────────────────────────────────────────────────────────────
# 2. Feature analytics service — SQLite persistence & deduplication
# ───────────────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Provide a fresh SQLite database for each test."""
    return str(tmp_path / "test_agent_eval.db")


@pytest.fixture
def analytics_service(tmp_db):
    """Create a FeatureAnalyticsService pointed at a temp DB."""
    # Monkey-patch db_service.db_path before importing
    from app.services import db as db_module
    original_path = db_module.db_service.db_path
    db_module.db_service.db_path = tmp_db

    from importlib import reload
    import app.services.feature_analytics_service as fas_module
    reload(fas_module)
    svc = fas_module.FeatureAnalyticsService()

    yield svc

    db_module.db_service.db_path = original_path


class TestObservationDeduplication:
    """Observations keyed by (run_id, capability) must not double-count."""

    def test_same_run_not_double_counted(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        model = "test-model"

        # Simulate completing a run twice (e.g., re-submission)
        with analytics_service._connect() as conn:
            analytics_service._upsert_observation(
                conn, f"{run_id}::reliability", model, "reliability",
                run_id, 1, 0, {"verified": True}
            )
            analytics_service._upsert_observation(
                conn, f"{run_id}::reliability", model, "reliability",
                run_id, 1, 0, {"verified": True}
            )
            conn.commit()

        # Only one observation should exist
        with analytics_service._connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM capability_observations WHERE run_id=? AND capability='reliability'",
                (run_id,)
            ).fetchone()[0]
        assert count == 1

    def test_different_runs_counted_separately(self, analytics_service):
        model = "test-model"
        run_ids = [f"run_{uuid.uuid4().hex[:8]}" for _ in range(3)]

        with analytics_service._connect() as conn:
            for rid in run_ids:
                analytics_service._upsert_observation(
                    conn, f"{rid}::reliability", model, "reliability",
                    rid, 1, 0, {}
                )
            conn.commit()

        with analytics_service._connect() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM capability_observations WHERE model_name=? AND capability='reliability'",
                (model,)
            ).fetchone()[0]
        assert count == 3

    def test_profile_aggregates_sum_correctly(self, analytics_service):
        model = "test-model"
        run_ids = [f"run_{uuid.uuid4().hex[:8]}" for _ in range(4)]

        with analytics_service._connect() as conn:
            for i, rid in enumerate(run_ids):
                s, f = (1, 0) if i < 3 else (0, 1)
                analytics_service._upsert_observation(
                    conn, f"{rid}::coding", model, "coding", rid, s, f, {}
                )
            conn.commit()

        with analytics_service._connect() as conn:
            row = conn.execute(
                "SELECT total_successes, total_failures FROM capability_profiles_v2 "
                "WHERE model_name=? AND capability='coding'",
                (model,)
            ).fetchone()
        assert row["total_successes"] == 3
        assert row["total_failures"] == 1


class TestCodingCapabilityEvidence:

    def test_coding_uses_test_suite_result_not_verifier_outcome(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        analytics_service.record_stage(
            run_id=run_id,
            stage="completed",
            success=False,
            model_name="test-model",
            details={"passed_tests": 4, "tests_total": 4},
            task_verified_success=False,
        )

        profiles = analytics_service.get_capability_profiles(model_name="test-model")["profiles"]
        by_capability = {profile["capability"]: profile for profile in profiles}
        assert by_capability["coding"]["successes"] == 1
        assert by_capability["coding"]["failures"] == 0
        assert by_capability["reliability"]["successes"] == 0
        assert by_capability["reliability"]["failures"] == 1

    def test_coding_fails_when_any_captured_test_fails(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        analytics_service.record_stage(
            run_id=run_id,
            stage="completed",
            success=True,
            model_name="test-model",
            details={"passed_tests": 3, "tests_total": 4},
            task_verified_success=True,
        )

        profiles = analytics_service.get_capability_profiles(model_name="test-model")["profiles"]
        coding = next(profile for profile in profiles if profile["capability"] == "coding")
        assert coding["successes"] == 0
        assert coding["failures"] == 1

    def test_older_coding_observations_are_reinterpreted_from_test_evidence(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        with analytics_service._connect() as conn:
            analytics_service._upsert_observation(
                conn,
                f"{run_id}::coding",
                "test-model",
                "coding",
                run_id,
                0,
                1,
                {"tests_passed": 4, "tests_total": 4},
            )
            conn.commit()

        profiles = analytics_service.get_capability_profiles(model_name="test-model")["profiles"]
        coding = next(profile for profile in profiles if profile["capability"] == "coding")
        assert coding["successes"] == 1
        assert coding["failures"] == 0


# ───────────────────────────────────────────────────────────────────────────
# 3. Recovery episode accounting
# ───────────────────────────────────────────────────────────────────────────

class TestRecoveryEpisodes:

    def test_unresolved_episode_not_counted_as_success(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        analytics_service.record_recovery_episode(
            episode_id=ep_id,
            run_id=run_id,
            model_name="test-model",
            failure_type="test_failure",
            original_error="AssertionError: expected 401",
            failure_timestamp="2026-01-01T00:00:00Z",
            original_failure_resolved=False,  # NOT resolved
            regression_tests_passed=None,
            final_verified_outcome="FAILED",
        )
        summary = analytics_service.get_recovery_summary(run_id)
        assert summary["resolved_episodes"] == 0
        assert summary["total_episodes"] == 1

    def test_resolved_episode_counted(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        analytics_service.record_recovery_episode(
            episode_id=ep_id,
            run_id=run_id,
            model_name="test-model",
            failure_type="test_failure",
            original_error="AssertionError",
            failure_timestamp="2026-01-01T00:00:00Z",
            original_failure_resolved=True,
            regression_tests_passed=True,
            final_verified_outcome="PASSED",
        )
        summary = analytics_service.get_recovery_summary(run_id)
        assert summary["resolved_episodes"] == 1
        assert summary["recovery_rate"] == pytest.approx(1.0, abs=1e-3)

    def test_regression_failure_not_counted_as_success(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        analytics_service.record_recovery_episode(
            episode_id=ep_id,
            run_id=run_id,
            model_name="test-model",
            failure_type="test_failure",
            original_error="some error",
            failure_timestamp="2026-01-01T00:00:00Z",
            original_failure_resolved=True,   # original fixed
            regression_tests_passed=False,     # but regressions broke!
            final_verified_outcome="FAILED",
        )
        summary = analytics_service.get_recovery_summary(run_id)
        assert summary["resolved_episodes"] == 0

    def test_recovery_duration_calculated(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        analytics_service.record_recovery_episode(
            episode_id=ep_id,
            run_id=run_id,
            model_name="test-model",
            failure_type="test_failure",
            original_error="error",
            failure_timestamp="2026-01-01T00:00:00Z",
            recovery_start_timestamp="2026-01-01T00:00:10Z",
            recovery_end_timestamp="2026-01-01T00:01:10Z",  # 60s later
            original_failure_resolved=True,
            regression_tests_passed=True,
        )
        summary = analytics_service.get_recovery_summary(run_id)
        assert summary["mean_recovery_duration_seconds"] == pytest.approx(60.0, abs=1.0)

    def test_duplicate_episode_id_does_not_double_count(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        for _ in range(3):
            analytics_service.record_recovery_episode(
                episode_id=ep_id,
                run_id=run_id,
                model_name="test-model",
                failure_type="test_failure",
                original_error="error",
                failure_timestamp="2026-01-01T00:00:00Z",
                original_failure_resolved=True,
                regression_tests_passed=True,
            )
        summary = analytics_service.get_recovery_summary(run_id)
        assert summary["total_episodes"] == 1

    def test_human_intervention_flag_not_fabricated(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ep_id = f"ep_{uuid.uuid4().hex[:10]}"
        analytics_service.record_recovery_episode(
            episode_id=ep_id,
            run_id=run_id,
            model_name="test-model",
            failure_type="tool_failure",
            original_error="import error",
            failure_timestamp="2026-01-01T00:00:00Z",
            original_failure_resolved=False,
            human_intervention=False,  # explicitly no human intervention
        )
        with analytics_service._connect() as conn:
            row = conn.execute(
                "SELECT human_intervention FROM recovery_episodes WHERE episode_id=?",
                (ep_id,)
            ).fetchone()
        assert row["human_intervention"] == 0


# ───────────────────────────────────────────────────────────────────────────
# 4. Insufficient evidence behaviour
# ───────────────────────────────────────────────────────────────────────────

class TestInsufficientEvidence:

    def test_profiles_show_insufficient_when_empty(self, analytics_service):
        result = analytics_service.get_capability_profiles()
        # No profiles → empty list, not fabricated scores
        assert result["profiles"] == []

    def test_unverified_legacy_duration_aggregate_is_not_displayed(self, analytics_service):
        with analytics_service._connect() as conn:
            conn.execute(
                """INSERT INTO capability_profiles_v2
                   (model_name, capability, total_successes, total_failures,
                    duration_values_json, extra_json, updated_at)
                   VALUES (?, 'efficiency', 0, 0, ?, '{}', '2026-10-13T00:00:00')""",
                ("test-model", json.dumps([47299.3])),
            )
            conn.commit()

        result = analytics_service.get_capability_profiles(model_name="test-model")
        assert not any(
            profile["capability"] == "efficiency"
            for profile in result["profiles"]
        )

    def test_recovery_summary_insufficient_when_empty(self, analytics_service):
        result = analytics_service.get_recovery_summary("nonexistent_run")
        assert result["evidence_status"] == "insufficient_evidence"

    def test_legacy_recovery_stats_match_recovery_panel_shape(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        analytics_service.record_recovery_stats(
            run_id=run_id,
            recovery_attempts=[{"resolved": True, "failure_reason": "test_failure"}],
            test_results=[{}, {}],
            elapsed_seconds=63.0,
        )

        result = analytics_service.get_recovery_summary(run_id)
        assert result["total_episodes"] == 1
        assert result["resolved_episodes"] == 1
        assert result["mean_recovery_duration_seconds"] == 63.0
        assert result["evidence_status"] == "measured"
        assert result["failure_type_breakdown"]["test_failure"]["attempts"] == 1

    def test_legacy_run_with_no_recovery_is_not_reported_as_missing_data(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        analytics_service.record_recovery_stats(
            run_id=run_id,
            recovery_attempts=[],
            test_results=[{}],
            elapsed_seconds=0.5,
        )

        result = analytics_service.get_recovery_summary(run_id)
        assert result["total_episodes"] == 0
        assert result["evidence_status"] == "no_recovery_needed"
        assert "No test failures" in result["note"]

    def test_predictor_shows_insufficient_data_without_a_trained_model(self, analytics_service):
        status = analytics_service.get_predictor_status()
        assert "Insufficient" in status["supervised_status"]
        assert not status["can_train"]


# ───────────────────────────────────────────────────────────────────────────
# 5. Trajectory label propagation
# ───────────────────────────────────────────────────────────────────────────

class TestTrajectoryLabels:

    def test_labels_set_at_completion(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        # Insert a fake trajectory step
        with analytics_service._connect() as conn:
            conn.execute(
                """INSERT INTO trajectory_features
                   (run_id, step_index, step_timestamp, stage, event_type,
                    cumulative_errors, cumulative_test_failures, repeated_messages,
                    steps_without_progress, constraint_violations, elapsed_seconds,
                    label_task_failed, created_at)
                   VALUES (?,0,?,?,?,0,0,0,0,0,1.0,NULL,?)""",
                (run_id, "2026-01-01T00:00:00Z", "testing", "test_failed", "2026-01-01T00:00:00Z")
            )
            conn.commit()

        # Initially label is NULL
        with analytics_service._connect() as conn:
            row = conn.execute(
                "SELECT label_task_failed FROM trajectory_features WHERE run_id=? AND step_index=0",
                (run_id,)
            ).fetchone()
        assert row["label_task_failed"] is None

        # Finalize with task_failed=True
        analytics_service.finalize_run_labels(run_id, task_failed=True)

        with analytics_service._connect() as conn:
            row = conn.execute(
                "SELECT label_task_failed FROM trajectory_features WHERE run_id=? AND step_index=0",
                (run_id,)
            ).fetchone()
        assert row["label_task_failed"] == 1

    def test_labels_do_not_leak_between_runs(self, analytics_service):
        run_a = f"run_{uuid.uuid4().hex[:8]}"
        run_b = f"run_{uuid.uuid4().hex[:8]}"

        for rid in [run_a, run_b]:
            with analytics_service._connect() as conn:
                conn.execute(
                    """INSERT INTO trajectory_features
                       (run_id, step_index, step_timestamp, stage, event_type,
                        cumulative_errors, cumulative_test_failures, repeated_messages,
                        steps_without_progress, constraint_violations, elapsed_seconds,
                        label_task_failed, created_at)
                       VALUES (?,0,?,?,?,0,0,0,0,0,1.0,NULL,?)""",
                    (rid, "2026-01-01T00:00:00Z", "testing", "test_failed", "2026-01-01T00:00:00Z")
                )
                conn.commit()

        analytics_service.finalize_run_labels(run_a, task_failed=True)

        # run_b label should remain NULL
        with analytics_service._connect() as conn:
            row = conn.execute(
                "SELECT label_task_failed FROM trajectory_features WHERE run_id=?",
                (run_b,)
            ).fetchone()
        assert row["label_task_failed"] is None


# ───────────────────────────────────────────────────────────────────────────
# 6. No fabricated values
# ───────────────────────────────────────────────────────────────────────────

class TestNoFabricatedValues:

    def test_capability_profile_has_no_arbitrary_100_score(self, analytics_service):
        """Ensure profiles do not silently output 100.0 scores with no data."""
        result = analytics_service.get_capability_profiles()
        for profile in result["profiles"]:
            if profile.get("measurement_type") == "binary":
                # Profiles expose the raw observed ratio, not a prior-adjusted score.
                assert "score" not in profile, "Old hard-coded 'score' field found"
                assert "observed_rate" in profile
                assert "posterior_mean" not in profile

    def test_agent_artifact_outcomes_populate_capability_profiles_without_priors(self, analytics_service):
        model = "artifact-model"
        with analytics_service._connect() as conn:
            conn.execute(
                """CREATE TABLE agent_proficiency_observations (
                    run_id TEXT, agent_id TEXT, model_name TEXT, metric_name TEXT,
                    successes INTEGER, failures INTEGER, details_json TEXT,
                    continuous_value REAL, is_valid INTEGER
                )"""
            )
            conn.executemany(
                """INSERT INTO agent_proficiency_observations
                   (run_id, agent_id, model_name, metric_name, successes, failures,
                    details_json, continuous_value, is_valid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("run1", "planner", model, "plan_feasibility_rate", 3, 1,
                     json.dumps({"measurement_basis": "Matched files / planned and changed path union."}),
                     None, 1),
                    ("run-invalid", "planner", "none", "plan_feasibility_rate", 0, 0,
                     "{}", None, 0),
                ],
            )
            conn.commit()

        result = analytics_service.get_capability_profiles(model_name=model)
        planner = next(p for p in result["profiles"] if p["capability"] == "planner")
        assert planner["display_name"] == "Codebase Analyst & Planner Agent"
        assert planner["successes"] == 3
        assert planner["failures"] == 1
        assert planner["observed_rate"] == pytest.approx(0.75)
        assert planner["evidence_status"] == "measured"
        assert planner["measurement_basis"] == "Matched files / planned and changed path union."
        assert "posterior_mean" not in planner

    def test_get_run_analytics_does_not_expose_rule_based_prediction(self, analytics_service):
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        # Record one stage event to populate tables
        with analytics_service._connect() as conn:
            conn.execute(
                """INSERT INTO feature_events
                   (run_id, model_name, stage, event_type, success,
                    details_json, elapsed_seconds, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (run_id, "test-model", "testing", "test_failed", 0, "{}", 1.5, "2026-01-01T00:00:00Z")
            )
            conn.execute(
                """INSERT INTO prediction_log
                   (run_id, step_index, risk_score, risk_reasons_json,
                    model_version, intervention_triggered, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (run_id, 0, 0.17, "[]", "rule_baseline_v1", 0, "2026-01-01T00:00:00Z")
            )
            conn.commit()

        analytics = analytics_service.get_run_analytics(run_id)
        pred = analytics["failure_prediction"]
        assert pred["is_trained_model"] is False
        assert pred["prediction_type"] == "unavailable"
        assert "risk_score" not in pred

    def test_no_overall_weighted_score(self, analytics_service):
        result = analytics_service.get_capability_profiles()
        assert "overall_score" not in result
        assert "weighted_score" not in result
        assert "aggregate_score" not in result


# ───────────────────────────────────────────────────────────────────────────
# 7. Capability estimator math — no scipy dependency
# ───────────────────────────────────────────────────────────────────────────

class TestEstimatorFallback:
    """Ensure the module works even when scipy is absent."""

    def test_fallback_approximation_within_bounds(self):
        """Patch scipy away and verify fallback stays in [0,1]."""
        import app.services.capability_estimator as ce_module
        original = ce_module._SCIPY_AVAILABLE
        try:
            ce_module._SCIPY_AVAILABLE = False
            from app.services.capability_estimator import compute_beta_binomial as compute
            est = compute("reliability", successes=5, failures=5)
            assert 0.0 <= (est.credible_interval_lower or 0.0)
            assert (est.credible_interval_upper or 1.0) <= 1.0
        finally:
            ce_module._SCIPY_AVAILABLE = original


# ───────────────────────────────────────────────────────────────────────────
# 8. API response structure (without real HTTP server)
# ───────────────────────────────────────────────────────────────────────────

class TestAPIResponseStructure:
    """Light structural tests — ensure routes return expected keys."""

    def setup_method(self):
        """Fast client setup."""
        from fastapi.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_capabilities_endpoint_returns_profiles_key(self):
        resp = self.client.get("/api/features/capabilities")
        assert resp.status_code == 200
        body = resp.json()
        assert "profiles" in body
        assert "note" in body

    def test_predictor_status_endpoint(self):
        resp = self.client.get("/api/features/predictor/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "supervised_status" in body
        assert "can_train" in body
        assert "labelled_trajectories" in body

    def test_capabilities_profiles_no_score_field(self):
        """Binary profiles must not contain the old 'score' field."""
        resp = self.client.get("/api/features/capabilities")
        assert resp.status_code == 200
        for profile in resp.json()["profiles"]:
            if profile.get("measurement_type") == "binary":
                assert "score" not in profile

    def test_run_analytics_has_prediction_not_labelled_as_measured(self):
        """Analytics must label prediction as heuristic, not observed."""
        # Use a fake run_id that won't exist
        resp = self.client.get("/api/features/nonexistent_run_000")
        assert resp.status_code == 200
        body = resp.json()
        pred = body.get("failure_prediction", {})
        assert pred.get("is_trained_model") is False
