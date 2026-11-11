"""
Ingestion Lambda — triggered by EventBridge on a schedule.

Fetches live crypto prices from the free CoinGecko API, writes them as a
Parquet file to the S3 raw bucket, and emits a custom EventBridge event so the
processing side knows new data has landed. Metrics go to CloudWatch.

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


def fetch_prices() -> pd.DataFrame:
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

    ingested_at = datetime.now(timezone.utc)
    rows = []
    for coin_id, v in raw.items():
        rows.append(
            {
                "coin_id": coin_id,
                "price_usd": v.get("usd"),
                "market_cap_usd": v.get("usd_market_cap"),
                "volume_24h_usd": v.get("usd_24h_vol"),
                "change_24h_pct": v.get("usd_24h_change"),
                "ingested_at": ingested_at,
            }
        )
    return pd.DataFrame(rows)


def put_metric(name: str, value: float) -> None:
    cloudwatch.put_metric_data(
        Namespace="CryptoPipeline/Ingestion",
        MetricData=[{"MetricName": name, "Value": value, "Unit": "Count"}],
    )


def handler(event, context):
    df = fetch_prices()

    # Partition the key by date/hour so Databricks can read incrementally.
    now = datetime.now(timezone.utc)
    key = (
        f"raw/crypto_prices/dt={now:%Y-%m-%d}/hour={now:%H}/"
        f"prices_{now:%Y%m%dT%H%M%S}.parquet"
    )

    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    s3.put_object(Bucket=RAW_BUCKET, Key=key, Body=buf.getvalue())

    # Tell the processing side that fresh raw data exists.
    events.put_events(
        Entries=[
            {
                "Source": "crypto.pipeline",
                "DetailType": "RawPricesLanded",
                "Detail": json.dumps({"bucket": RAW_BUCKET, "key": key, "rows": len(df)}),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )

    put_metric("RowsIngested", len(df))
    return {"statusCode": 200, "rows": len(df), "key": key}
