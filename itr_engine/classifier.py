"""Public API for deterministic ITR classification."""

from itr_engine.evaluator import evaluate_profile


def classify_itr(canonical_tax_profile):
    """Classify a canonical tax profile into a candidate ITR form.

    The result is deterministic and pure rule-based. This function does not use
    AI, LLMs, network calls, or external mutable state.
    """
    return evaluate_profile(canonical_tax_profile)
