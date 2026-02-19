"""Tests for configuration loading and data models."""

import tempfile
from pathlib import Path

import yaml

from agent_verify.config import (
    ExperimentConfig,
    HarnessConfig,
    RecoveryStrategyType,
    VerificationGranularity,
    VerificationMethod,
    load_config,
)


def test_harness_config_defaults():
    config = HarnessConfig()
    assert config.verification_method == VerificationMethod.NONE
    assert config.verification_granularity == VerificationGranularity.TASK_END_ONLY
    assert config.recovery_strategy == RecoveryStrategyType.RETRY_IN_CONTEXT
    assert config.max_iterations == 50


def test_experiment_config_from_dict():
    config = ExperimentConfig(
        experiment_id="test_001",
        harness=HarnessConfig(
            verification_method=VerificationMethod.TEST_EXECUTION,
            verification_granularity=VerificationGranularity.PER_FEATURE,
        ),
    )
    assert config.experiment_id == "test_001"
    assert config.harness.verification_method == VerificationMethod.TEST_EXECUTION
    assert config.num_trials == 3


def test_load_config_from_yaml():
    data = {
        "experiment_id": "yaml_test",
        "benchmark": "swebench",
        "num_trials": 2,
        "harness": {
            "verification_method": "test_execution",
            "verification_granularity": "per_feature",
            "recovery_strategy": "fresh_restart",
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        tmp_path = f.name

    config = load_config(tmp_path)
    assert config.experiment_id == "yaml_test"
    assert config.harness.verification_method == VerificationMethod.TEST_EXECUTION
    assert config.harness.recovery_strategy == RecoveryStrategyType.FRESH_RESTART
    assert config.num_trials == 2

    Path(tmp_path).unlink()
