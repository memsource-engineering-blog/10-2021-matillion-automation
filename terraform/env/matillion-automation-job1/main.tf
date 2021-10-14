module "matillion-automation-job1" {
  source = "../../modules/matillion-automation-job"

  vpc_name          = var.vpc_name
  image_name_filter = "matillion-for-snowflake-version-1.51.8"
  instance_type     = "m5.large"

  matillion_project_group_name = "ETL"
  matillion_project_name       = "Automation"
  matillion_job_name           = "Job1"
  matillion_environment_name   = "QA"
  lambda_name_prefix           = "matillion-auto"
  instance_name_prefix         = "matillion-auto"
  need_static_address          = true
  slack_webhook                = "https://hooks.slack.com/services/some/channel/logs"
  slack_alert_webhook          = "https://hooks.slack.com/services/some/channel/alerts"
  secrets_s3_bucket            = "secrets.my-bucket.com"

  start_type     = "cron"
  cron = "cron(15 2 * * ? *)"
}
