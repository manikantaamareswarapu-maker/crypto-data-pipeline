variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "owner" {
  description = "Tag applied to all resources"
  type        = string
  default     = "manikanta"
}

variable "coins" {
  description = "Comma-separated CoinGecko coin ids to ingest"
  type        = string
  default     = "bitcoin,ethereum,solana,cardano,dogecoin"
}

variable "schedule_expression" {
  description = "EventBridge schedule for ingestion"
  type        = string
  default     = "rate(5 minutes)"
}

variable "databricks_host" {
  description = "Databricks workspace URL"
  type        = string
  default     = ""
}

variable "databricks_token" {
  description = "Databricks PAT (prefer Secrets Manager in production)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "databricks_job_id" {
  description = "Databricks job id to run on new raw data"
  type        = string
  default     = ""
}
