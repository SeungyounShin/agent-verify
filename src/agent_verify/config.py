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
    base_url: str | None = None   # For openai-compatible providers (vLLM, ollama, etc.)
    api_key: str | None = None    # API key (defaults to env var or "dummy" for local)


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
        "execute bash commands, search code, and use git. Complete the given task "
        "by modifying the codebase as needed.\n\n"
        "## Tool Usage Guidelines\n"
        "- Use `file_read` to read files. ALWAYS read a file before editing it.\n"
        "- Use `file_edit` for small, targeted changes (preferred). Use `file_write` "
        "only to create new files or rewrite entire files.\n"
        "- Use `grep` to search file contents (regex patterns). Do NOT use `bash` "
        "with grep/rg for searching.\n"
        "- Use `glob` to find files by name pattern. Do NOT use `bash` with find/ls "
        "for locating files.\n"
        "- Use `bash` for running tests, git operations, and other shell commands.\n\n"
        "## Workflow\n"
        "1. Start by understanding the issue: read relevant files, search for key "
        "terms, understand the codebase structure.\n"
        "2. Make targeted edits. Prefer small, precise changes over large rewrites.\n"
        "3. After editing, run relevant tests to verify your fix.\n"
        "4. If tests fail, read the error output carefully, re-read the code, and "
        "try a different approach.\n\n"
        "When you believe the task is complete, state 'TASK_COMPLETE' in your response."
    )
    workspace_dir: str = "/tmp/agent-workspace"


class ExperimentConfig(BaseModel):
    """Configuration for a full experiment run."""
    experiment_id: str
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    benchmark: str = "swebench"
    dataset_name: str = "princeton-nlp/SWE-bench_Verified"
    split: str = "test"
    instance_ids: list[str] = Field(default_factory=list)
    num_trials: int = 3
    output_dir: str = "results"
    seed: int = 42


def load_config(path: str | Path) -> ExperimentConfig:
    """Load experiment config from YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return ExperimentConfig(**data)
