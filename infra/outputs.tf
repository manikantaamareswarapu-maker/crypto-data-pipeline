output "raw_bucket" {
  value       = aws_s3_bucket.raw.bucket
  description = "S3 bucket for raw parquet"
}

output "processed_bucket" {
  value       = aws_s3_bucket.processed.bucket
  description = "S3 bucket for processed Delta Lake tables"
}

output "ingestion_lambda" {
  value = aws_lambda_function.ingestion.function_name
}

output "processing_trigger_lambda" {
  value = aws_lambda_function.processing_trigger.function_name
}
