"""Expected guarded feature transformation for the demonstration."""


def calculate_monthly_spend(total_spend: float, account_age_months: int) -> float:
    """Return average spend per active account month."""
    if account_age_months <= 0:
        return 0.0
    return total_spend / account_age_months
