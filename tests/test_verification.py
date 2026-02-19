"""Tests for verification module."""

from agent_verify.benchmark.base import Task
from agent_verify.config import VerificationMethod
from agent_verify.context import Context
from agent_verify.verification import create_verifier
from agent_verify.verification.none import NoVerification
from agent_verify.verification.test_execution import TestExecutionVerifier


def _make_task(**kwargs) -> Task:
    defaults = {"task_id": "test_task", "description": "Test task"}
    defaults.update(kwargs)
    return Task(**defaults)


def test_no_verification():
    verifier = NoVerification()
    ctx = Context()
    task = _make_task()
    result = verifier.verify(ctx, task)
    assert result.passed is True


def test_create_verifier_factory():
    v0 = create_verifier(VerificationMethod.NONE)
    assert isinstance(v0, NoVerification)

    v2 = create_verifier(VerificationMethod.TEST_EXECUTION)
    assert isinstance(v2, TestExecutionVerifier)


def test_test_execution_no_command():
    verifier = TestExecutionVerifier()
    ctx = Context()
    task = _make_task(test_command="")
    result = verifier.verify(ctx, task)
    assert result.passed is False
    assert "No test command" in result.message


def test_test_execution_passing():
    import tempfile
    verifier = TestExecutionVerifier()
    ctx = Context()
    with tempfile.TemporaryDirectory() as tmpdir:
        task = _make_task(test_command="true", workspace_dir=tmpdir)
        result = verifier.verify(ctx, task)
        assert result.passed is True


def test_test_execution_failing():
    import tempfile
    verifier = TestExecutionVerifier()
    ctx = Context()
    with tempfile.TemporaryDirectory() as tmpdir:
        task = _make_task(test_command="false", workspace_dir=tmpdir)
        result = verifier.verify(ctx, task)
        assert result.passed is False
