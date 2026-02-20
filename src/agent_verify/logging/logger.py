"""Structured JSON experiment logger."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agent_verify.context import ToolCall
from agent_verify.verification.base import VerificationResult


class ExperimentLogger:
    """Logs all experiment events as structured JSON lines."""

    def __init__(self, experiment_id: str, output_dir: str = "results"):
        self.experiment_id = experiment_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_dir / f"{experiment_id}.jsonl"
        self._events: list[dict[str, Any]] = []

    def _write_event(self, event: dict[str, Any]) -> None:
        event["experiment_id"] = self.experiment_id
        event["timestamp"] = time.time()
        self._events.append(event)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event, default=str) + "\n")

    def log_run_start(self, task_id: str, config: dict[str, Any]) -> None:
        self._write_event({
            "event": "run_start",
            "task_id": task_id,
            "config": config,
        })

    def log_llm_call(
        self,
        task_id: str,
        iteration: int,
        input_tokens: int,
        output_tokens: int,
        stop_reason: str,
        has_tool_use: bool,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        self._write_event({
            "event": "llm_call",
            "task_id": task_id,
            "iteration": iteration,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
            "cost_usd": round(cost_usd, 6),
            "stop_reason": stop_reason,
            "has_tool_use": has_tool_use,
        })

    def log_tool_call(self, task_id: str, tool_call: ToolCall) -> None:
        self._write_event({
            "event": "tool_call",
            "task_id": task_id,
            "tool_name": tool_call.tool_name,
            "duration_seconds": tool_call.duration_seconds,
        })

    def log_verification(
        self,
        task_id: str,
        verification: VerificationResult,
        method: str,
    ) -> None:
        self._write_event({
            "event": "verification",
            "task_id": task_id,
            "method": method,
            "passed": verification.passed,
            "message": verification.message[:1000],
            "token_cost": verification.token_cost,
        })

    def log_recovery(
        self,
        task_id: str,
        strategy: str,
        attempt: int,
    ) -> None:
        self._write_event({
            "event": "recovery",
            "task_id": task_id,
            "strategy": strategy,
            "attempt": attempt,
        })

    def log_run_end(self, task_id: str, result: dict[str, Any]) -> None:
        self._write_event({
            "event": "run_end",
            "task_id": task_id,
            "result": result,
        })
