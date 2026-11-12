"""
Ingestion Lambda — triggered by EventBridge on a schedule.

Fetches live crypto prices from the free CoinGecko API, VALIDATES each record
against a schema, writes the valid rows as a Parquet file to the S3 raw bucket,
and emits an EventBridge event so the processing side knows new data landed.

Data hygiene is enforced here, at the point of capture: a record that fails
validation never reaches S3. Rejected records are counted and sent to
CloudWatch so bad data is visible instead of silent.

Env vars (set by Terraform):
    RAW_BUCKET        target S3 bucket for raw parquet
    EVENT_BUS_NAME    custom EventBridge bus (or "default")
    COINS             comma-separated CoinGecko ids
"""

from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone

import boto3
import pandas as pd
import requests

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

s3 = boto3.client("s3")
events = boto3.client("events")
cloudwatch = boto3.client("cloudwatch")

RAW_BUCKET = os.environ["RAW_BUCKET"]
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")
COINS = os.environ.get("COINS", "bitcoin,ethereum,solana,cardano,dogecoin")

# --- Schema: the contract every record must satisfy before it can land. ---
# field name -> (expected python type, is it required?)
SCHEMA = {
    "coin_id": (str, True),
    "price_usd": ((int, float), True),
    "market_cap_usd": ((int, float), False),
    "volume_24h_usd": ((int, float), False),
    "change_24h_pct": ((int, float), False),
    "ingested_at": (str, True),
}


def fetch_prices() -> list[dict]:
    params = {
        "ids": COINS,
        "vs_currencies": "usd",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
        "include_24hr_change": "true",
    }
    resp = requests.get(COINGECKO_URL, params=params, timeout=10)
    resp.raise_for_status()
    raw = resp.json()

    ingested_at = datetime.now(timezone.utc).isoformat()
    records = []
    for coin_id, v in raw.items():
        records.append(
            {
                "coin_id": coin_id,
                "price_usd": v.get("usd"),
                "market_cap_usd": v.get("usd_market_cap"),
                "volume_24h_usd": v.get("usd_24h_vol"),
                "change_24h_pct": v.get("usd_24h_change"),
                "ingested_at": ingested_at,
            }
        )
    return records


def is_valid(record: dict) -> tuple[bool, str]:
    """Check one record against SCHEMA. Returns (ok, reason_if_not)."""
    for field, (expected_type, required) in SCHEMA.items():
        value = record.get(field)

        if value is None:
            if required:
                return False, f"missing required field '{field}'"
            continue  # optional + absent is fine

        if not isinstance(value, expected_type):
            return False, f"field '{field}' has wrong type: {type(value).__name__}"

    # Business rule: a price must be a positive number.
    if record["price_usd"] <= 0:
        return False, "price_usd must be greater than 0"

    # Business rule: coin_id must not be blank.
    if not record["coin_id"].strip():
        return False, "coin_id is empty"

    return True, ""


def validate(records: list[dict]) -> tuple[list[dict], int]:
    """Split records into valid ones and a count of rejects (logged)."""
    valid, rejected = [], 0
    for r in records:
        ok, reason = is_valid(r)
        if ok:
            valid.append(r)
        else:
            rejected += 1
            print(f"REJECTED {r.get('coin_id', '?')}: {reason}")
    return valid, rejected


def put_metric(name: str, value: float) -> None:
    cloudwatch.put_metric_data(
        Namespace="CryptoPipeline/Ingestion",
        MetricData=[{"MetricName": name, "Value": value, "Unit": "Count"}],
    )


def handler(event, context):
    records = fetch_prices()

    # Enforce the schema at the point of capture.
    valid, rejected = validate(records)
    put_metric("RowsRejected", rejected)

    if not valid:
        # Nothing clean to write — fail loudly rather than land an empty file.
        put_metric("RowsIngested", 0)
        raise ValueError(f"All {len(records)} records failed validation; nothing written.")

    df = pd.DataFrame(valid)

    now = datetime.now(timezone.utc)
    key = (
        f"raw/crypto_prices/dt={now:%Y-%m-%d}/hour={now:%H}/"
        f"prices_{now:%Y%m%dT%H%M%S}.parquet"
    )

    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=buf.getvalue())

    events.put_events(
        Entries=[
            {
                "Source": "crypto.pipeline",
                "DetailType": "RawPricesLanded",
                "Detail": json.dumps({"bucket": RAW_BUCKET, "key": key, "rows": len(valid)}),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )

    put_metric("RowsIngested", len(valid))
    return {
        "statusCode": 200,
        "ingested": len(valid),
        "rejected": rejected,
        "key": key,
    }
