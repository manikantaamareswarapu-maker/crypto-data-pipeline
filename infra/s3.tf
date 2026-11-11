# Raw and processed buckets. Names must be globally unique, so a random
# suffix is appended.

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "raw" {
  bucket = "${local.name}-raw-${random_id.suffix.hex}"
  tags   = local.tags
}

resource "aws_s3_bucket" "processed" {
  bucket = "${local.name}-processed-${random_id.suffix.hex}"
  tags   = local.tags
}

# Let S3 publish object-created events to EventBridge (not used by the custom
# bus flow, but handy if you later switch to native S3->EventBridge triggers).
resource "aws_s3_bucket_notification" "raw_events" {
  bucket      = aws_s3_bucket.raw.id
  eventbridge = true
}
