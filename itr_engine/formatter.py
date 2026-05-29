"""Output formatting for deterministic ITR classification."""


def format_result(candidate_itr, reason_codes, missing_fields, confidence):
    """Return the stable public classifier response shape."""
    return {
        "candidate_itr": candidate_itr,
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "missing_fields": sorted(set(missing_fields)),
        "confidence": confidence,
    }
