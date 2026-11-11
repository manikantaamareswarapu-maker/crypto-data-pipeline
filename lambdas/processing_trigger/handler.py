"""
Processing Trigger Lambda — invoked by EventBridge when raw prices land.

Kicks off the Databricks job that transforms the raw Parquet into a modeled
Delta Lake table. Uses the Databricks Jobs REST API.

Env vars (set by Terraform / secrets):
    DATABRICKS_HOST   e.g. https://dbc-xxxx.cloud.databricks.com
    DATABRICKS_TOKEN  personal access token (store in Secrets Manager)
    DATABRICKS_JOB_ID numeric id of the job to run
"""

from __future__ import annotations

import json
import os

import boto3
import requests

cloudwatch = boto3.client("cloudwatch")

HOST = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN = os.environ["DATABRICKS_TOKEN"]
JOB_ID = os.environ["DATABRICKS_JOB_ID"]


def handler(event, context):
    # The raw file that landed is passed through from the ingestion event.
    detail = event.get("detail", {})

    resp = requests.post(
        f"{HOST}/api/2.1/jobs/run-now",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "job_id": int(JOB_ID),
            "notebook_params": {
                "raw_bucket": detail.get("bucket", ""),
                "raw_key": detail.get("key", ""),
            },
        },
        timeout=15,
    )
    resp.raise_for_status()
    run_id = resp.json().get("run_id")

    cloudwatch.put_metric_data(
        Namespace="CryptoPipeline/Processing",
        MetricData=[{"MetricName": "DatabricksRunsTriggered", "Value": 1, "Unit": "Count"}],
    )
    return {"statusCode": 200, "run_id": run_id, "detail": detail}
