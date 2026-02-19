"""Tests for recovery strategies."""

from agent_verify.benchmark.base import Task
from agent_verify.config import RecoveryStrategyType
from agent_verify.context import Context
from agent_verify.recovery import create_recovery_strategy
from agent_verify.recovery.fresh import FreshRestart
from agent_verify.recovery.retry import RetryInContext
from agent_verify.verification.base import VerificationResult


def _make_context() -> Context:
    ctx = Context()
    ctx.add_user_message("Fix the bug")
    ctx.add_assistant_message([{"type": "text", "text": "I will fix it"}])
    ctx.iteration_count = 5
    return ctx


def _make_task() -> Task:
    return Task(task_id="test", description="Fix the bug in foo.py")


def _make_failure() -> VerificationResult:
    return VerificationResult(passed=False, message="Tests failed: 2 errors")


def test_retry_in_context():
    strategy = RetryInContext()
    ctx = _make_context()
    original_len = len(ctx.messages)

    new_ctx = strategy.recover(ctx, _make_failure(), _make_task())

    assert new_ctx is ctx  # Same context object
    assert len(new_ctx.messages) == original_len + 1  # Feedback appended
    assert "VERIFICATION FAILED" in new_ctx.messages[-1]["content"]
    assert new_ctx.recovery_count == 1


def test_fresh_restart():
    strategy = FreshRestart()
    ctx = _make_context()

    new_ctx = strategy.recover(ctx, _make_failure(), _make_task())

    assert new_ctx is not ctx  # New context
    assert len(new_ctx.messages) == 1  # Only restart message
    assert "Previous Attempt Result" in new_ctx.messages[0]["content"]
    assert new_ctx.recovery_count == 1
    # Cumulative metrics carried over
    assert new_ctx.iteration_count == ctx.iteration_count


def test_create_recovery_factory():
    r1 = create_recovery_strategy(RecoveryStrategyType.RETRY_IN_CONTEXT)
    assert isinstance(r1, RetryInContext)

    r3 = create_recovery_strategy(RecoveryStrategyType.FRESH_RESTART)
    assert isinstance(r3, FreshRestart)
