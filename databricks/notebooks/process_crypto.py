# Databricks notebook source
# MAGIC %md
# MAGIC # Process crypto prices -> Delta Lake
# MAGIC Reads raw Parquet from S3, cleans and models it into a star schema,
# MAGIC and writes Delta tables to the processed S3 bucket.
# MAGIC Triggered by the Processing Trigger Lambda via the Jobs API.

# COMMAND ----------

from pyspark.sql import functions as F

# Params passed in by the triggering Lambda (notebook_params).
dbutils.widgets.text("raw_bucket", "")
dbutils.widgets.text("raw_key", "")
dbutils.widgets.text("processed_bucket", "")

raw_bucket = dbutils.widgets.get("raw_bucket")
processed_bucket = dbutils.widgets.get("processed_bucket")

RAW_PATH = f"s3://{raw_bucket}/raw/crypto_prices/"
PROCESSED_PATH = f"s3://{processed_bucket}/processed/"

# COMMAND ----------

# Read all raw partitions. Schema is inferred from the Parquet files.
raw = spark.read.parquet(RAW_PATH)

# COMMAND ----------

# Staging: clean + type, drop null prices.
stg = (
    raw.where(F.col("price_usd").isNotNull())
    .withColumn("ingested_at", F.col("ingested_at").cast("timestamp"))
    .withColumn("ingested_minute", F.date_trunc("minute", F.col("ingested_at")))
)

# COMMAND ----------

# Dimension: one row per coin.
dim_coin = (
    stg.select("coin_id")
    .distinct()
    .withColumn("symbol_guess", F.upper(F.substring("coin_id", 1, 4)))
    .withColumnRenamed("coin_id", "coin_name")
    .withColumn("coin_id", F.col("coin_name"))
)

# COMMAND ----------

# Fact: one row per coin per minute (the dashboard grain).
fct_price_snapshots = (
    stg.groupBy("coin_id", "ingested_minute")
    .agg(
        F.avg("price_usd").alias("avg_price_usd"),
        F.max("price_usd").alias("max_price_usd"),
        F.min("price_usd").alias("min_price_usd"),
        F.avg("market_cap_usd").alias("avg_market_cap_usd"),
        F.avg("volume_24h_usd").alias("avg_volume_24h_usd"),
        F.avg("change_24h_pct").alias("avg_change_24h_pct"),
        F.count("*").alias("reading_count"),
    )
)

# COMMAND ----------

# Write Delta Lake tables (overwrite the fact's affected partitions in prod;
# full overwrite is fine for a learning project).
(dim_coin.write.format("delta").mode("overwrite")
    .save(f"{PROCESSED_PATH}/dim_coin"))

(fct_price_snapshots.write.format("delta").mode("overwrite")
    .partitionBy("coin_id")
    .save(f"{PROCESSED_PATH}/fct_price_snapshots"))

print("Delta tables written to", PROCESSED_PATH)
