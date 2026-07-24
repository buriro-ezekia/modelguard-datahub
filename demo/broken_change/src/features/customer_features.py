"""Candidate feature transformation containing the demonstrated regression."""


def calculate_monthly_spend(total_spend: float, account_age_months: int) -> float:
    """Return average spend per active account month."""
    return total_spend / account_age_months
