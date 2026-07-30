#!/usr/bin/env python3
"""Load an idempotent ModelGuard ML lineage graph into a live DataHub instance."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/live_datahub_complete/ml_lineage_manifest.json"
ACTOR_URN = "urn:li:corpuser:modelguard"
OWNER_URN = "urn:li:corpGroup:data-platform"


def _field(
    models: Any,
    *,
    name: str,
    native_type: str,
    data_type: Any,
    description: str,
) -> Any:
    return models.SchemaFieldClass(
        fieldPath=name,
        type=models.SchemaFieldDataTypeClass(type=data_type),
        nativeDataType=native_type,
        description=description,
        lastModified=models.AuditStampClass(
            time=int(time.time() * 1000),
            actor=ACTOR_URN,
        ),
    )


def _emit(emitter: Any, wrapper_type: Any, urn: str, aspect: Any) -> dict[str, str]:
    emitter.emit_mcp(wrapper_type(entityUrn=urn, aspect=aspect))
    return {"urn": urn, "aspect": type(aspect).__name__}


def load_graph(*, output: Path) -> dict[str, Any]:
    """Create the live ML graph and return a manifest of all emitted entities."""

    try:
        import datahub.emitter.mce_builder as builder
        import datahub.metadata.schema_classes as models
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.emitter.rest_emitter import DatahubRestEmitter
    except ImportError as exc:
        raise RuntimeError(
            'DataHub support is not installed. Run: pip install -e ".[datahub]"'
        ) from exc

    gms_url = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080").rstrip("/")
    token = os.getenv("DATAHUB_GMS_TOKEN") or None
    emitter = DatahubRestEmitter(gms_server=gms_url, token=token)
    emitter.test_connection()

    platform = "snowflake"
    environment = "PROD"
    raw_dataset_urn = builder.make_dataset_urn(
        platform,
        "modelguard.raw.customers",
        environment,
    )
    feature_dataset_urn = builder.make_dataset_urn(
        platform,
        "modelguard.features.customer_features",
        environment,
    )
    training_dataset_urn = builder.make_dataset_urn(
        platform,
        "modelguard.training.churn_training_dataset",
        environment,
    )

    flow_urn = builder.make_data_flow_urn(
        orchestrator="airflow",
        flow_id="modelguard_churn_feature_pipeline",
        cluster="prod",
    )
    feature_job_urn = builder.make_data_job_urn_with_flow(
        flow_urn,
        "build_customer_features",
    )
    training_job_urn = builder.make_data_job_urn_with_flow(
        flow_urn,
        "build_churn_training_dataset",
    )

    feature_table_name = "modelguard_customer_features"
    primary_key_urn = builder.make_ml_primary_key_urn(
        feature_table_name,
        "customer_id",
    )
    monthly_spend_feature_urn = builder.make_ml_feature_urn(
        feature_table_name,
        "monthly_spend",
    )
    account_age_feature_urn = builder.make_ml_feature_urn(
        feature_table_name,
        "account_age_months",
    )
    feature_table_urn = builder.make_ml_feature_table_urn(
        "feast",
        feature_table_name,
    )

    model_group_urn = builder.make_ml_model_group_urn(
        "mlflow",
        "modelguard-churn-models",
        environment,
    )
    model_urn = builder.make_ml_model_urn(
        "mlflow",
        "churn-model-v3",
        environment,
    )
    deployment_urn = builder.make_ml_model_deployment_urn(
        "kserve",
        "churn-api-prod",
        environment,
    )

    emitted: list[dict[str, str]] = []
    datasets = (
        (
            raw_dataset_urn,
            "raw_customers",
            "Source customer records for the ModelGuard live ML lineage proof.",
            [
                _field(
                    models,
                    name="customer_id",
                    native_type="VARCHAR",
                    data_type=models.StringTypeClass(),
                    description="Stable customer identifier.",
                ),
                _field(
                    models,
                    name="total_spend",
                    native_type="DOUBLE",
                    data_type=models.NumberTypeClass(),
                    description="Lifetime customer spend before feature transformation.",
                ),
                _field(
                    models,
                    name="account_created_at",
                    native_type="TIMESTAMP",
                    data_type=models.TimeTypeClass(),
                    description="Customer account creation timestamp.",
                ),
            ],
        ),
        (
            feature_dataset_urn,
            "customer_features",
            "Production customer features investigated by ModelGuard.",
            [
                _field(
                    models,
                    name="customer_id",
                    native_type="VARCHAR",
                    data_type=models.StringTypeClass(),
                    description="Stable customer identifier.",
                ),
                _field(
                    models,
                    name="monthly_spend",
                    native_type="DOUBLE",
                    data_type=models.NumberTypeClass(),
                    description="Average customer spend per active account month.",
                ),
                _field(
                    models,
                    name="account_age_months",
                    native_type="INTEGER",
                    data_type=models.NumberTypeClass(),
                    description="Completed months since account creation.",
                ),
            ],
        ),
        (
            training_dataset_urn,
            "churn_training_dataset",
            "Approved training dataset for the production churn model.",
            [
                _field(
                    models,
                    name="customer_id",
                    native_type="VARCHAR",
                    data_type=models.StringTypeClass(),
                    description="Stable customer identifier.",
                ),
                _field(
                    models,
                    name="monthly_spend",
                    native_type="DOUBLE",
                    data_type=models.NumberTypeClass(),
                    description="Model input feature derived from customer spend.",
                ),
                _field(
                    models,
                    name="account_age_months",
                    native_type="INTEGER",
                    data_type=models.NumberTypeClass(),
                    description="Model input feature representing account tenure.",
                ),
                _field(
                    models,
                    name="churned",
                    native_type="BOOLEAN",
                    data_type=models.BooleanTypeClass(),
                    description="Training target for customer churn.",
                ),
            ],
        ),
    )

    for dataset_urn, name, description, fields in datasets:
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                dataset_urn,
                models.DatasetPropertiesClass(
                    name=name,
                    description=description,
                    customProperties={
                        "project": "ModelGuard",
                        "evidence": "live-datahub-ml-lineage",
                    },
                ),
            )
        )
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                dataset_urn,
                models.SchemaMetadataClass(
                    schemaName=name,
                    platform=builder.make_data_platform_urn(platform),
                    version=0,
                    hash="modelguard-live-v1",
                    platformSchema=models.OtherSchemaClass(rawSchema=""),
                    fields=fields,
                ),
            )
        )
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                dataset_urn,
                models.OwnershipClass(
                    owners=[
                        models.OwnerClass(
                            owner=OWNER_URN,
                            type=models.OwnershipTypeClass.TECHNICAL_OWNER,
                        )
                    ]
                ),
            )
        )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            flow_urn,
            models.DataFlowInfoClass(
                name="ModelGuard churn feature pipeline",
                description=(
                    "Builds customer features and the approved churn training dataset."
                ),
                project="ModelGuard",
            ),
        )
    )

    jobs = (
        (
            feature_job_urn,
            "build_customer_features",
            [raw_dataset_urn],
            [feature_dataset_urn],
        ),
        (
            training_job_urn,
            "build_churn_training_dataset",
            [feature_dataset_urn],
            [training_dataset_urn],
        ),
    )
    for job_urn, name, inputs, outputs in jobs:
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                job_urn,
                models.DataJobInfoClass(
                    name=name,
                    type="SnapshotETL",
                    flowUrn=flow_urn,
                    description=f"ModelGuard live lineage job: {name}.",
                ),
            )
        )
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                job_urn,
                models.DataJobInputOutputClass(
                    inputDatasets=inputs,
                    outputDatasets=outputs,
                ),
            )
        )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            primary_key_urn,
            models.MLPrimaryKeyPropertiesClass(
                description="Primary customer identifier for the feature table.",
                dataType="TEXT",
                sources=[training_dataset_urn],
            ),
        )
    )

    features = (
        (
            monthly_spend_feature_urn,
            "Average monthly spend used by the churn model.",
            "CONTINUOUS",
        ),
        (
            account_age_feature_urn,
            "Completed account age in months used by the churn model.",
            "COUNT",
        ),
    )
    for feature_urn, description, data_type in features:
        emitted.append(
            _emit(
                emitter,
                MetadataChangeProposalWrapper,
                feature_urn,
                models.MLFeaturePropertiesClass(
                    description=description,
                    dataType=data_type,
                    sources=[training_dataset_urn],
                ),
            )
        )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            feature_table_urn,
            models.MLFeatureTablePropertiesClass(
                description="Feature table used to train churn-model-v3.",
                mlFeatures=[monthly_spend_feature_urn, account_age_feature_urn],
                mlPrimaryKeys=[primary_key_urn],
                customProperties={
                    "owner_team": "data-platform",
                    "serving_tier": "production",
                },
            ),
        )
    )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            model_group_urn,
            models.MLModelGroupPropertiesClass(
                name="ModelGuard churn models",
                description="Versioned production churn models protected by ModelGuard.",
                customProperties={"project": "ModelGuard"},
            ),
        )
    )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            deployment_urn,
            models.MLModelDeploymentPropertiesClass(
                description="Production KServe deployment for churn-model-v3.",
                status=models.DeploymentStatusClass.IN_SERVICE,
                version="3",
                customProperties={
                    "namespace": "modelguard",
                    "service": "churn-api-prod",
                    "validation": "f1-restored-0.842",
                },
            ),
        )
    )

    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            model_urn,
            models.MLModelPropertiesClass(
                name="churn-model-v3",
                description=(
                    "Production churn model used by the ModelGuard regression scenario."
                ),
                type="Gradient Boosted Classifier",
                mlFeatures=[monthly_spend_feature_urn, account_age_feature_urn],
                groups=[model_group_urn],
                deployments=[deployment_urn],
                customProperties={
                    "baseline_f1": "0.842",
                    "regressed_f1": "0.771",
                    "recovered_f1": "0.842",
                    "invalid_values_before": "37",
                    "invalid_values_after": "0",
                },
            ),
        )
    )
    emitted.append(
        _emit(
            emitter,
            MetadataChangeProposalWrapper,
            model_urn,
            models.OwnershipClass(
                owners=[
                    models.OwnerClass(
                        owner=OWNER_URN,
                        type=models.OwnershipTypeClass.TECHNICAL_OWNER,
                    )
                ]
            ),
        )
    )

    manifest = {
        "status": "loaded",
        "gms_url": gms_url,
        "generated_at_epoch_ms": int(time.time() * 1000),
        "raw_dataset_urn": raw_dataset_urn,
        "feature_dataset_urn": feature_dataset_urn,
        "training_dataset_urn": training_dataset_urn,
        "flow_urn": flow_urn,
        "feature_job_urn": feature_job_urn,
        "training_job_urn": training_job_urn,
        "primary_key_urn": primary_key_urn,
        "monthly_spend_feature_urn": monthly_spend_feature_urn,
        "account_age_feature_urn": account_age_feature_urn,
        "feature_table_urn": feature_table_urn,
        "model_group_urn": model_group_urn,
        "model_urn": model_urn,
        "deployment_urn": deployment_urn,
        "expected_path": [
            raw_dataset_urn,
            feature_job_urn,
            feature_dataset_urn,
            training_job_urn,
            training_dataset_urn,
            monthly_spend_feature_urn,
            model_urn,
            deployment_urn,
        ],
        "emitted": emitted,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        manifest = load_graph(output=args.output.resolve())
    except Exception as exc:
        print(f"ModelGuard live ML lineage load failed: {exc}")
        return 1

    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\nLive ML lineage loaded: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
