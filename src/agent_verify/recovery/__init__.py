"""Recovery strategies (R1-R3)."""

from agent_verify.config import RecoveryStrategyType

from .base import RecoveryStrategy
from .compact import CompactAndRetry
from .fresh import FreshRestart
from .retry import RetryInContext


def create_recovery_strategy(strategy_type: RecoveryStrategyType) -> RecoveryStrategy:
    """Factory function to create a recovery strategy from config."""
    mapping: dict[RecoveryStrategyType, type[RecoveryStrategy]] = {
        RecoveryStrategyType.RETRY_IN_CONTEXT: RetryInContext,
        RecoveryStrategyType.COMPACT_AND_RETRY: CompactAndRetry,
        RecoveryStrategyType.FRESH_RESTART: FreshRestart,
    }
    cls = mapping[strategy_type]
    return cls()
