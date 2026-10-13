"""Beta-Binomial capability estimator for binary outcomes.

Implements an online Bayesian estimator for binary task/recovery success.
Uses a Beta(alpha_prior, beta_prior) conjugate prior. After observing
s successes and f failures the posterior is Beta(alpha_prior+s, beta_prior+f).

The 95% credible interval is computed via scipy.stats.beta.ppf which is a
validated numerical library; no hand-rolled approximation is used.

Only binary outcomes (task success, recovery success) are estimated with
this approach. Continuous measurements (duration, token counts) are stored
as raw observations and summarised with descriptive statistics, not Bayesian
posteriors.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, List

# Lazy-import scipy so the module is still importable if scipy is absent
try:
    from scipy.stats import beta as _beta_dist  # type: ignore
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


from datetime import datetime, timezone

@dataclass
class BetaBinomialEstimate:
    """Result from one capability posterior computation."""

    capability: str
    successes: int
    failures: int
    sample_size: int

    # Configurable prior (stored for reproducibility)
    alpha_prior: float
    beta_prior: float

    # Posterior parameters
    posterior_alpha: float
    posterior_beta: float

    # Derived statistics
    observed_rate: Optional[float]          # raw s/(s+f), None when n==0
    posterior_mean: float                   # alpha/(alpha+beta)
    credible_interval_lower: Optional[float]  # 2.5th percentile
    credible_interval_upper: Optional[float]  # 97.5th percentile

    # Evidence quality
    evidence_status: str                    # "estimated" | "insufficient_evidence"
    note: str = ""

    # Optional dynamic extension fields
    raw_successes: Optional[int] = None
    raw_failures: Optional[int] = None
    recency_decay_applied: bool = False
    task_type: Optional[str] = None
    difficulty: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "capability": self.capability,
            "successes": self.successes,
            "failures": self.failures,
            "sample_size": self.sample_size,
            "alpha_prior": self.alpha_prior,
            "beta_prior": self.beta_prior,
            "posterior_alpha": self.posterior_alpha,
            "posterior_beta": self.posterior_beta,
            "observed_rate": self.observed_rate,
            "posterior_mean": self.posterior_mean,
            "credible_interval_lower": self.credible_interval_lower,
            "credible_interval_upper": self.credible_interval_upper,
            "evidence_status": self.evidence_status,
            "note": self.note,
            "scipy_used": _SCIPY_AVAILABLE,
            "raw_successes": self.raw_successes if self.raw_successes is not None else self.successes,
            "raw_failures": self.raw_failures if self.raw_failures is not None else self.failures,
            "recency_decay_applied": self.recency_decay_applied,
            "task_type": self.task_type,
            "difficulty": self.difficulty,
        }


@dataclass
class ContinuousSummary:
    """Descriptive summary for continuous-valued measurements."""

    measurement: str
    unit: str
    values: List[float] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def mean(self) -> Optional[float]:
        return sum(self.values) / len(self.values) if self.values else None

    @property
    def minimum(self) -> Optional[float]:
        return min(self.values) if self.values else None

    @property
    def maximum(self) -> Optional[float]:
        return max(self.values) if self.values else None

    @property
    def stdev(self) -> Optional[float]:
        if len(self.values) < 2:
            return None
        m = self.mean
        assert m is not None
        return math.sqrt(sum((v - m) ** 2 for v in self.values) / (len(self.values) - 1))

    def to_dict(self) -> dict:
        return {
            "measurement": self.measurement,
            "unit": self.unit,
            "n": self.n,
            "mean": round(self.mean, 4) if self.mean is not None else None,
            "min": round(self.minimum, 4) if self.minimum is not None else None,
            "max": round(self.maximum, 4) if self.maximum is not None else None,
            "stdev": round(self.stdev, 4) if self.stdev is not None else None,
            "evidence_status": "measured" if self.n > 0 else "insufficient_evidence",
        }


def compute_beta_binomial(
    capability: str,
    successes: float | int,
    failures: float | int,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    sample_size: Optional[int] = None,
    raw_successes: Optional[int] = None,
    raw_failures: Optional[int] = None,
    recency_decay_applied: bool = False,
    task_type: Optional[str] = None,
    difficulty: Optional[str] = None,
) -> BetaBinomialEstimate:
    """Compute Beta-Binomial posterior for a binary capability metric.

    Supports integer raw counts or recency-decayed effective weights.
    """
    raw_s = int(round(raw_successes if raw_successes is not None else successes))
    raw_f = int(round(raw_failures if raw_failures is not None else failures))
    n = sample_size if sample_size is not None else (raw_s + raw_f)

    eff_s = float(successes)
    eff_f = float(failures)

    pa = alpha_prior + eff_s
    pb = beta_prior + eff_f
    posterior_mean = pa / (pa + pb)

    observed_rate: Optional[float] = (raw_s / n) if n > 0 else None

    lower: Optional[float] = None
    upper: Optional[float] = None

    if _SCIPY_AVAILABLE:
        lower = float(_beta_dist.ppf(0.025, pa, pb))
        upper = float(_beta_dist.ppf(0.975, pa, pb))
    else:
        # Fallback: Wilson-like approximation
        z = 1.96
        centre = posterior_mean
        denom = max(eff_s + eff_f, 1.0)
        margin = z * math.sqrt(max(centre * (1 - centre), 1e-9) / denom)
        lower = max(0.0, centre - margin)
        upper = min(1.0, centre + margin)

    if n == 0:
        status = "insufficient_evidence"
        note = "No eligible observations recorded yet."
    elif n < 3:
        status = "estimated"
        note = f"Low sample (n={n}); prior has substantial influence. Treat as provisional."
    else:
        status = "estimated"
        note = f"Beta-Binomial posterior from {n} eligible task-level observations{' (recency-weighted)' if recency_decay_applied else ''}."

    return BetaBinomialEstimate(
        capability=capability,
        successes=raw_s,
        failures=raw_f,
        sample_size=n,
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
        posterior_alpha=round(pa, 4),
        posterior_beta=round(pb, 4),
        observed_rate=round(observed_rate, 4) if observed_rate is not None else None,
        posterior_mean=round(posterior_mean, 4),
        credible_interval_lower=round(lower, 4) if lower is not None else None,
        credible_interval_upper=round(upper, 4) if upper is not None else None,
        evidence_status=status,
        note=note,
        raw_successes=raw_s,
        raw_failures=raw_f,
        recency_decay_applied=recency_decay_applied,
        task_type=task_type,
        difficulty=difficulty,
    )


def compute_recency_weighted_counts(
    observations: List[dict],
    half_life_days: float = 14.0
) -> tuple[float, float, int, int]:
    """Calculate recency-decayed effective successes and failures.

    w_i = exp(-lambda * delta_t_days), lambda = ln(2) / half_life_days.
    """
    if not observations:
        return 0.0, 0.0, 0, 0

    now_dt = datetime.now(timezone.utc)
    decay_lambda = math.log(2) / max(0.1, half_life_days)
    eff_s = 0.0
    eff_f = 0.0
    raw_s = 0
    raw_f = 0

    for obs in observations:
        s = int(obs.get("successes", 0))
        f = int(obs.get("failures", 0))
        raw_s += s
        raw_f += f

        created_str = obs.get("created_at")
        w = 1.0
        if created_str:
            try:
                obs_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                delta_days = max(0.0, (now_dt - obs_dt).total_seconds() / 86400.0)
                w = math.exp(-decay_lambda * delta_days)
            except Exception:
                w = 1.0
        eff_s += s * w
        eff_f += f * w

    return round(eff_s, 4), round(eff_f, 4), raw_s, raw_f


def detect_capability_drift(
    recent_outcomes: List[int],
    historical_outcomes: List[int],
    capability: str = "capability"
) -> dict:
    """Detect performance drift between recent and historical outcomes."""
    n_rec = len(recent_outcomes)
    n_hist = len(historical_outcomes)

    if n_rec < 3 or n_hist < 3:
        return {
            "capability": capability,
            "drift_status": "insufficient_data",
            "recent_rate": round(sum(recent_outcomes) / n_rec, 4) if n_rec else None,
            "historical_rate": round(sum(historical_outcomes) / n_hist, 4) if n_hist else None,
            "delta": None,
            "note": f"Insufficient sample sizes for drift detection (recent={n_rec}, historical={n_hist}, min 3 each required)."
        }

    p_rec = sum(recent_outcomes) / n_rec
    p_hist = sum(historical_outcomes) / n_hist
    delta = round(p_rec - p_hist, 4)

    if delta >= 0.15:
        status = "improving"
    elif delta <= -0.15:
        status = "degrading"
    else:
        status = "stable"

    return {
        "capability": capability,
        "drift_status": status,
        "recent_rate": round(p_rec, 4),
        "historical_rate": round(p_hist, 4),
        "delta": delta,
        "note": f"Performance is {status} (recent {round(p_rec*100, 1)}% vs historical {round(p_hist*100, 1)}%, delta: {delta:+0.3f})."
    }


class CapabilityPolicyEngine:
    """Translates capability profiles into actionable operational decisions."""

    @staticmethod
    def get_retry_budget(posterior_mean: float, base_budget: int = 3, sample_size: int = 0) -> int:
        """Calibrate retry budget: stop unproductive retries if recovery is low."""
        if sample_size >= 3 and posterior_mean < 0.35:
            return max(1, base_budget - 1)
        elif sample_size >= 3 and posterior_mean >= 0.70:
            return base_budget + 1
        return base_budget

    @staticmethod
    def route_model(task_type: str, candidate_profiles: dict[str, float]) -> str:
        """Route task to candidate model with highest capability posterior."""
        if not candidate_profiles:
            return "qwen2.5-coder:7b"
        return max(candidate_profiles.items(), key=lambda kv: kv[1])[0]

    @staticmethod
    def evaluate_risk_action(risk_score: float, model_reliability: float = 0.5) -> str:
        """Select action based on risk score calibrated against model reliability."""
        threshold_offset = 0.05 if model_reliability < 0.4 else 0.0
        if risk_score >= (0.85 - threshold_offset):
            return "stop"
        elif risk_score >= (0.75 - threshold_offset):
            return "ask_human"
        elif risk_score >= (0.60 - threshold_offset):
            return "switch_strategy"
        elif risk_score >= (0.35 - threshold_offset):
            return "inspect"
        return "continue"
