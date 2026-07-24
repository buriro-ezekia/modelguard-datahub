# ModelGuard Validated Repair Report

- **Repair:** `repair-d359e2c30c02`
- **Diagnosis:** `diag-2f83c16bbe31`
- **Hypothesis:** `H001`
- **Status:** `validated`
- **Strategy:** `guarded_division`
- **Source workspace unchanged:** `True`

## Proposed change

Insert an explicit non-positive denominator guard before the diagnosed division while preserving all other source lines.

```diff
--- a/src/features/customer_features.py
+++ b/src/features/customer_features.py
@@ -3,4 +3,6 @@
 
 def calculate_monthly_spend(total_spend: float, account_age_months: int) -> float:
     """Return average spend per active account month."""
+    if account_age_months <= 0:
+        return 0.0
     return total_spend / account_age_months
```

## Patch guard

Approved: **True**

- PASS — leading diagnosis has high confidence and score >= 0.8
- PASS — patch changes at most 1 file(s)
- PASS — path is relative and traversal-safe: src/features/customer_features.py
- PASS — line and token limits pass for src/features/customer_features.py

## Independent validation

- PASS — `{python} -m py_compile src/features/customer_features.py` (exit 0, 0.0371s)
- PASS — `{python} -m pytest tests/test_customer_features.py -q` (exit 0, 0.2123s)
- PASS — `{python} evaluate_model.py --output artifacts/post_repair_evaluation.json` (exit 0, 0.0380s)

## Metric gate

- Baseline: `0.842`
- Repaired candidate: `0.842`
- Maximum regression: `0.02`
- Gate status: **passed**

## Safety statement

Validation occurred in a temporary workspace. This report does not merge or apply the patch to the source branch; a human-reviewed pull request remains required.
