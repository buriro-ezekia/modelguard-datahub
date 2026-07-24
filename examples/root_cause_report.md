# ModelGuard Root-Cause Report

- **Diagnosis:** `diag-2f83c16bbe31`
- **Status:** `ranked`
- **Repository:** `buriro-ezekia/modelguard-datahub`
- **Commit:** `a817f42`
- **Model:** `urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)`
- **Failed metric:** `f1_score`

## Leading diagnosis

**Changed feature transformation introduced invalid values**

Confidence: **high** (`1.0000`)

A pull-request change touches model input fields on the DataHub lineage path, and candidate observations show an adverse change.

Affected asset: `urn:li:dataset:(urn:li:dataPlatform:dbt,analytics.customer_features,PROD)`

Affected fields: `account_age_months`, `monthly_spend`, `total_spend`

## Ranked hypotheses

### 1. Changed feature transformation introduced invalid values

- Category: `feature_transformation`
- Score: `1.0000` (high)
- Asset: `urn:li:dataset:(urn:li:dataPlatform:dbt,analytics.customer_features,PROD)`
- Supporting evidence: `E001`, `E002`, `E006`, `E010`, `E011`
- Counter-evidence: none

A pull-request change touches model input fields on the DataHub lineage path, and candidate observations show an adverse change.

Recommended checks:
- Reproduce the transformation on boundary-value rows.
- Compare baseline and candidate field distributions.
- Rerun evaluation after the smallest guarded correction.

### 2. Upstream source values caused the model regression

- Category: `source_data_quality`
- Score: `0.6025` (medium)
- Asset: `urn:li:dataset:(urn:li:dataPlatform:snowflake,raw.raw_customers,PROD)`
- Supporting evidence: `E001`, `E010`, `E011`, `E009`, `E007`
- Counter-evidence: `E002`

Boundary or invalid values are present upstream, but a direct code change may better explain why they became harmful in this candidate.

Recommended checks:
- Compare source validity rates across baseline and candidate windows.
- Confirm whether the same source values existed before the change.

### 3. A schema or nullability contract changed

- Category: `schema_contract`
- Score: `0.2775` (low)
- Asset: `urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)`
- Supporting evidence: `E001`, `E003`, `E004`
- Counter-evidence: `E002`

The input schema is relevant, but no direct schema migration is shown unless the changed-file evidence explicitly cites one.

Recommended checks:
- Compare baseline and candidate DataHub schema aspects.
- Inspect native-type and nullability changes for model inputs.

## Evidence registry

### E001 — metric

f1_score changed from 0.842 to 0.771 with status failed.

Source: `phase1:evaluation` · Strength: `1.000`

### E002 — change

Modified file src/features/customer_features.py at a817f42.

Source: `repository:src/features/customer_features.py` · Strength: `0.950`

### E003 — schema

Schema field monthly_spend has type DOUBLE and nullable=True.

Source: `datahub:urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)` · Strength: `0.650`

### E004 — schema

Schema field account_age_months has type INTEGER and nullable=False.

Source: `datahub:urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)` · Strength: `0.650`

### E005 — lineage

churn_training_dataset is 1 hop(s) upstream of the investigated model.

Source: `datahub:urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.churn_training_dataset,PROD)` · Strength: `0.850`

### E006 — lineage

customer_features is 2 hop(s) upstream of the investigated model.

Source: `datahub:urn:li:dataset:(urn:li:dataPlatform:dbt,analytics.customer_features,PROD)` · Strength: `0.750`

### E007 — lineage

raw_customers is 3 hop(s) upstream of the investigated model.

Source: `datahub:urn:li:dataset:(urn:li:dataPlatform:snowflake,raw.raw_customers,PROD)` · Strength: `0.650`

### E008 — lineage

churn-api-prod is 1 hop(s) downstream of the investigated model.

Source: `datahub:urn:li:mlModelDeployment:(urn:li:dataPlatform:kubernetes,churn-api-prod,PROD)` · Strength: `0.850`

### E009 — quality

{'baseline': 0.842, 'candidate': 0.771, 'metric': 'f1_score', 'status': 'failed', 'type': 'metric-regression'}

Source: `datahub:urn:li:mlModel:(urn:li:dataPlatform:mlflow,churn-model-v3,PROD)` · Strength: `0.850`

### E010 — observation

Candidate monthly_spend contains 37 infinite values; the baseline contains none.

Source: `ci:observation` · Strength: `0.950`

### E011 — observation

Twelve source rows have account_age_months equal to zero in both baseline and candidate data.

Source: `ci:observation` · Strength: `0.750`

## Warnings

- Diagnosis used deterministic fixture context, not a live DataHub instance.

## Safety statement

This report ranks hypotheses; it does not prove causality or authorise a code change. A repair must be independently generated, constrained and validated in Phase 4.
