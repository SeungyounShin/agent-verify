"""Configuration data models for the agent harness experiment."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class VerificationMethod(str, Enum):
    NONE = "none"                # V0
    SELF_REVIEW = "self_review"  # V1
    TEST_EXECUTION = "test_execution"  # V2
    SPEC_COMPARISON = "spec_comparison"  # V3
    E2E = "e2e"                  # V4


class VerificationGranularity(str, Enum):
    TASK_END_ONLY = "task_end_only"  # G1
    PER_FEATURE = "per_feature"      # G2
    PER_STEP = "per_step"            # G3


class RecoveryStrategyType(str, Enum):
    RETRY_IN_CONTEXT = "retry_in_context"      # R1
    COMPACT_AND_RETRY = "compact_and_retry"     # R2
    FRESH_RESTART = "fresh_restart"             # R3


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 8192
    temperature: float = 0.0


class HarnessConfig(BaseModel):
    """Configuration for a single agent harness run."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    verification_method: VerificationMethod = VerificationMethod.NONE
    verification_granularity: VerificationGranularity = VerificationGranularity.TASK_END_ONLY
    recovery_strategy: RecoveryStrategyType = RecoveryStrategyType.RETRY_IN_CONTEXT
    max_iterations: int = 50
    max_recovery_attempts: int = 3
    max_tokens_budget: int = 500_000
    timeout_seconds: int = 600
    system_prompt: str = (
        "You are a software engineering agent. You can read and write files, "
        "execute bash commands, and use git. Complete the given task by modifying "
        "the codebase as needed. When you believe the task is complete, state "
        "'TASK_COMPLETE' in your response."
    )
    workspace_dir: str = "/tmp/agent-workspace"


class ExperimentConfig(BaseModel):
    """Configuration for a full experiment run."""
    experiment_id: str
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    benchmark: str = "swebench"
    instance_ids: list[str] = Field(default_factory=list)
    num_trials: int = 3
    output_dir: str = "results"
    seed: int = 42


def load_config(path: str | Path) -> ExperimentConfig:
    """Load experiment config from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return ExperimentConfig(**data)
