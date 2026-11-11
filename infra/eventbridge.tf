# 1) Scheduled rule -> Ingestion Lambda.
resource "aws_cloudwatch_event_rule" "ingestion_schedule" {
  name                = "${local.name}-ingestion-schedule"
  schedule_expression = var.schedule_expression
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "ingestion" {
  rule = aws_cloudwatch_event_rule.ingestion_schedule.name
  arn  = aws_lambda_function.ingestion.arn
}

resource "aws_lambda_permission" "allow_schedule" {
  statement_id  = "AllowScheduleInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ingestion_schedule.arn
}

# 2) Custom event (RawPricesLanded) -> Processing Trigger Lambda.
resource "aws_cloudwatch_event_rule" "raw_landed" {
  name = "${local.name}-raw-landed"
  event_pattern = jsonencode({
    source      = ["crypto.pipeline"]
    detail-type = ["RawPricesLanded"]
  })
  tags = local.tags
}

resource "aws_cloudwatch_event_target" "processing" {
  rule = aws_cloudwatch_event_rule.raw_landed.name
  arn  = aws_lambda_function.processing_trigger.arn
}

resource "aws_lambda_permission" "allow_event" {
  statement_id  = "AllowEventInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.processing_trigger.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.raw_landed.arn
}
