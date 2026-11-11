# IAM role shared by both Lambdas.
resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.name}-lambda-policy"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["events:PutEvents"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Package the Lambda source. Run `make build` first to vendor dependencies
# into each function directory (see README).
data "archive_file" "ingestion" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/ingestion"
  output_path = "${path.module}/build/ingestion.zip"
}

data "archive_file" "processing_trigger" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/processing_trigger"
  output_path = "${path.module}/build/processing_trigger.zip"
}

resource "aws_lambda_function" "ingestion" {
  function_name    = "${local.name}-ingestion"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 256
  filename         = data.archive_file.ingestion.output_path
  source_code_hash = data.archive_file.ingestion.output_base64sha256

  environment {
    variables = {
      RAW_BUCKET     = aws_s3_bucket.raw.bucket
      EVENT_BUS_NAME = "default"
      COINS          = var.coins
    }
  }
  tags = local.tags
}

resource "aws_lambda_function" "processing_trigger" {
  function_name    = "${local.name}-processing-trigger"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 128
  filename         = data.archive_file.processing_trigger.output_path
  source_code_hash = data.archive_file.processing_trigger.output_base64sha256

  environment {
    variables = {
      DATABRICKS_HOST   = var.databricks_host
      DATABRICKS_TOKEN  = var.databricks_token
      DATABRICKS_JOB_ID = var.databricks_job_id
    }
  }
  tags = local.tags
}
