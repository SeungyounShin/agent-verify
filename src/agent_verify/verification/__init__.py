"""Verification strategies (V0-V4)."""

from agent_verify.config import VerificationMethod

from .base import VerificationResult, Verifier
from .e2e import E2EVerifier
from .none import NoVerification
from .self_review import SelfReviewVerifier
from .spec_comparison import SpecComparisonVerifier
from .test_execution import TestExecutionVerifier


def create_verifier(method: VerificationMethod) -> Verifier:
    """Factory function to create a verifier from config."""
    mapping: dict[VerificationMethod, type[Verifier]] = {
        VerificationMethod.NONE: NoVerification,
        VerificationMethod.SELF_REVIEW: SelfReviewVerifier,
        VerificationMethod.TEST_EXECUTION: TestExecutionVerifier,
        VerificationMethod.SPEC_COMPARISON: SpecComparisonVerifier,
        VerificationMethod.E2E: E2EVerifier,
    }
    cls = mapping[method]
    return cls()
