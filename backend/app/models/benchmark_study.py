"""Public benchmark configuration; evaluator answers are never part of a manifest."""
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudyFault(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['none', 'transient', 'timeout_after_commit', 'delay', 'noisy_observation'] = 'none'
    tool: Literal['read', 'checkpoint', 'apply_patch', 'run_checks', 'commit', 'notify'] = 'commit'
    occurrence: int = Field(default=1, ge=1, le=100)
    delay_seconds: float = Field(default=.05, ge=0, le=2, allow_inf_nan=False)

    @model_validator(mode='after')
    def valid_target(self):
        if self.kind == 'timeout_after_commit' and self.tool != 'commit':
            raise ValueError('Post-commit timeout requires the commit tool')
        return self


class StudyManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    manifest_version: Literal['2'] = '2'
    suite_version: Literal['software-studies-v2'] = 'software-studies-v2'
    environment_version: Literal['gateway-v2'] = 'gateway-v2'
    verifier_version: Literal['protected-checks-v2'] = 'protected-checks-v2'
    execution_mode: Literal['trusted_simulation', 'local_ollama', 'registered_adapter'] = 'trusted_simulation'
    adapter_id: str = Field(default='scripted-v2', min_length=1, max_length=100)
    adapter_version: str = Field(default='2', min_length=1, max_length=100)
    task_ids: list[Literal['sum_fix', 'empty_average', 'stable_unique', 'clamp', 'casefold']] = Field(default_factory=lambda:['sum_fix'], min_length=1, max_length=5)
    conditions: list[Literal['baseline', 'generic_retry', 'idempotent_retry', 'enhanced', 'no_prediction', 'no_diagnosis', 'memory_none', 'memory_full_history', 'memory_semantic', 'memory_goal_aware']] = Field(default_factory=lambda:['baseline', 'generic_retry', 'idempotent_retry'], min_length=1, max_length=10)
    scenario: Literal['normal', 'goal_adherence', 'memory_retention', 'tool_recovery', 'sustained_correctness', 'task_length', 'efficiency'] = 'normal'
    repetitions: int = Field(default=2, ge=1, le=20)
    task_lengths: list[int] = Field(default_factory=lambda:[5, 15], min_length=1, max_length=4)
    seed: int = Field(default=42, ge=0, le=2147483647)
    max_steps: int = Field(default=80, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    timeout_seconds: float = Field(default=30, gt=0, le=300, allow_inf_nan=False)
    fault: StudyFault = Field(default_factory=StudyFault)
    ambiguity: bool = False
    feedback_policy: Literal['none', 'fixture_clarification'] = 'none'
    model: str | None = Field(default=None, max_length=100)
    think: Literal[False] = False
    pilot_id: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,80}$')
    max_trials: int = Field(default=3, ge=1, le=3)
    max_model_calls: int = Field(default=15, ge=1, le=15)
    max_total_generated_tokens: int = Field(default=6000, ge=1, le=6000)
    max_output_tokens: int = Field(default=1000, ge=1, le=1000)
    model_timeout_seconds: float = Field(default=120, gt=0, le=300, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_study(self):
        for values in (self.task_ids, self.conditions, self.task_lengths):
            if len(values) != len(set(values)):
                raise ValueError('Duplicate task, condition or length')
        if any(n < 5 or n > 100 for n in self.task_lengths):
            raise ValueError('Lengths must be 5 through 100')
        if len(self.task_ids)*len(self.conditions)*len(self.task_lengths)*self.repetitions > 300:
            raise ValueError('At most 300 trials')
        if self.execution_mode == 'local_ollama':
            if self.model not in ('qwen3:8b', 'qwen3:1.7b') or not self.pilot_id or self.adapter_id != 'ollama-v1' or self.adapter_version != '1':
                raise ValueError('The approved pilot requires qwen3:8b or qwen3:1.7b, a persistent pilot_id, and ollama-v1 version 1')
            if len(self.task_ids)*len(self.conditions)*len(self.task_lengths)*self.repetitions > self.max_trials:
                raise ValueError('Pilot exceeds the maximum of three trials')
            if self.max_retries != 0:
                raise ValueError('The approved model pilot permits no automatic retries')
            if any(c not in ('baseline', 'memory_none', 'memory_full_history') for c in self.conditions):
                raise ValueError('Other ablations require a registered team adapter; they are not implemented by the Ollama controller')
        elif self.model is not None:
            raise ValueError('Model selection applies only to local_ollama')
        if self.execution_mode == 'trusted_simulation' and (self.adapter_id, self.adapter_version) != ('scripted-v2', '2'):
            raise ValueError('Trusted simulation uses scripted-v2 version 2')
        return self


class BenchmarkAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tool: Literal['read', 'checkpoint', 'clarify', 'apply_patch', 'run_checks', 'commit', 'notify']
    operation_id: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)


class EvidenceEvent(BaseModel):
    """Operator/evaluator ingestion contract, never accepted as agent ground truth."""
    model_config = ConfigDict(extra='forbid')
    event_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=100)
    step: int = Field(ge=0)
    timestamp: str
    source: Literal['evaluator', 'human', 'team_module', 'fixture']
    kind: Literal['prediction', 'drift', 'memory', 'attribution', 'human', 'intervention']
    version: str = Field(min_length=1, max_length=100)
    data: dict[str, Any]


class EvidenceBatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    events: list[EvidenceEvent] = Field(min_length=1, max_length=1000)
