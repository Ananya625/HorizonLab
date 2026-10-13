"""Versioned, bounded configurations for the trusted software-task simulator."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

TASK_IDS = ('sum_fix', 'empty_average', 'stable_unique', 'clamp', 'casefold')
CONDITIONS = ('baseline', 'generic_retry', 'idempotent_retry')


class FaultConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['none', 'transient', 'timeout_after_commit'] = 'none'
    tool: Literal['read', 'apply_patch', 'run_checks', 'commit', 'notify'] = 'commit'
    occurrence: int = Field(default=1, ge=1, le=100)

    @model_validator(mode='after')
    def validate_commit_timeout(self):
        if self.kind == 'timeout_after_commit' and self.tool != 'commit':
            raise ValueError('Post-commit timeout is only defined for commit')
        return self


class ExperimentManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    manifest_version: Literal['1'] = '1'
    suite_version: Literal['software-simulator-v1'] = 'software-simulator-v1'
    agent_version: Literal['scripted-agent-v1'] = 'scripted-agent-v1'
    environment_version: Literal['gateway-v1'] = 'gateway-v1'
    verifier_version: Literal['protected-checks-v1'] = 'protected-checks-v1'
    execution_mode: Literal['trusted_simulation'] = 'trusted_simulation'
    task_ids: list[Literal['sum_fix', 'empty_average', 'stable_unique', 'clamp', 'casefold']] = Field(default_factory=lambda: list(TASK_IDS), min_length=1, max_length=5)
    conditions: list[Literal['baseline', 'generic_retry', 'idempotent_retry']] = Field(default_factory=lambda: list(CONDITIONS), min_length=1, max_length=3)
    repetitions: int = Field(default=2, ge=1, le=20)
    seed: int = Field(default=42, ge=0, le=2147483647)
    task_lengths: list[int] = Field(default_factory=lambda: [5, 15], min_length=1, max_length=4)
    max_steps: int = Field(default=50, ge=1, le=200)
    timeout_seconds: float = Field(default=10, gt=0, le=60, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=5)
    fault: FaultConfig = Field(default_factory=FaultConfig)

    @model_validator(mode='after')
    def bounds(self):
        if any(n < 5 or n > 100 for n in self.task_lengths):
            raise ValueError('Task lengths must be between 5 and 100 actions')
        for values in (self.task_ids, self.conditions, self.task_lengths):
            if len(values) != len(set(values)):
                raise ValueError('Duplicate task, condition, or length')
        if len(self.task_ids)*len(self.conditions)*len(self.task_lengths)*self.repetitions > 300:
            raise ValueError('At most 300 trials per experiment')
        return self
