"""Versioned observational evidence; never an execution policy."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, model_validator


class WorkflowEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    event_id: str = Field(default_factory=lambda: uuid4().hex, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    task_id: str | None = None
    version: Literal['workflow-v1'] = 'workflow-v1'
    kind: Literal['action_start', 'action_result', 'attempt_start', 'attempt_end',
                  'verification', 'completion_claim', 'goal_snapshot', 'plan_snapshot', 'notice']
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action_id: str | None = None
    parent_action_id: str | None = None
    attempt_id: str | None = None
    recovery_id: str | None = None
    sub_goal_id: str | None = None
    goal_revision: str | None = None
    plan_revision: str | None = None
    category: Literal['tool', 'model', 'stage'] | None = None
    operation: str | None = Field(default=None, max_length=100)
    agent: str | None = Field(default=None, max_length=100)
    target: str | None = Field(default=None, max_length=300)
    arguments_hash: str | None = None
    before_state: str | None = None
    after_state: str | None = None
    observation_hash: str | None = None
    outcome: Literal['success', 'failed', 'error', 'rejected', 'unknown'] | None = None
    reason: str | None = Field(default=None, max_length=100)
    duration_seconds: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    intended_operation_id: str | None = None
    effect_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid_evidence(self):
        stamp = datetime.fromisoformat(self.timestamp)
        if stamp.tzinfo is None:
            raise ValueError('Event timestamps require a timezone')
        if self.kind.startswith('action_') and not (self.action_id and self.category and self.operation):
            raise ValueError('Action events require identity, category and operation')
        if self.kind == 'action_result' and self.outcome is None:
            raise ValueError('Action result requires an explicit outcome')
        if self.kind.startswith('attempt_') and not self.attempt_id:
            raise ValueError('Attempt events require identity')
        return self
