locals {
  full_job_name = "${var.matillion_job_name}_${var.matillion_environment_name}"
}

data "aws_iam_role" "matillion_lambda_role" {
  name = "matillion-automation-lambda-role"
}

data "aws_vpc" "vpc" {
  tags = {
    Name = var.vpc_name
  }
}

data "aws_subnet_ids" "private_subnet" {
  vpc_id = data.aws_vpc.vpc.id

  tags = {
    Name = "private_0"
  }
}

data "aws_security_group" "matillion_automation" {
  tags = {
    Name = "matillion-automation-lambda-security-group"
  }
}

##### Starting Matillion

resource "aws_lambda_layer_version" "lambda_layer_requests" {
  layer_name          = "requests"
  compatible_runtimes = ["python3.7"]

  filename         = "${path.module}/lambda/requests.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda/requests.zip")
}

resource "aws_lambda_function" "lambda_matillion_starting" {
  function_name    = "${var.lambda_name_prefix}_automation_${local.full_job_name}"
  runtime          = "python3.7"
  timeout          = 300
  role             = data.aws_iam_role.matillion_lambda_role.arn
  handler          = "matillion_starting_handler.lambda_handler"
  source_code_hash = filebase64sha256("${path.module}/lambda/matillion_starting_handler.zip")
  filename         = "${path.module}/lambda/matillion_starting_handler.zip"
  layers           = [aws_lambda_layer_version.lambda_layer_requests.arn]

  vpc_config {
    security_group_ids = [data.aws_security_group.matillion_automation.id]
    subnet_ids         = [tolist(data.aws_subnet_ids.private_subnet.ids)[0]]
  }

  environment {
    variables = {
      "INSTANCE_TYPE"        = var.instance_type
      "LAUNCH_TEMPLATE"      = var.launch_template_name
      "PROJECT_GROUP_NAME"   = var.matillion_project_group_name
      "PROJECT_NAME"         = var.matillion_project_name
      "JOB_NAME"             = var.matillion_job_name
      "ENVIRONMENT_NAME"     = var.matillion_environment_name
      "GIT_BRANCH"           = var.matillion_project_git_branch
      "SLACK_WEBHOOK"        = var.slack_webhook
      "IMAGE_NAME_FILTER"    = var.image_name_filter
      "NEED_STATIC_ADDRESS"  = var.need_static_address ? "true" : "false"
      "INSTANCE_NAME_PREFIX" = var.instance_name_prefix
      "SECRETS_S3_BUCKET"    = var.secrets_s3_bucket
    }
  }
}

resource "aws_cloudwatch_event_rule" "schedule_rule" {
  name                = "${var.lambda_name_prefix}-automation-${local.full_job_name}"
  description         = "Runs according to cron expression ${var.cron}"
  schedule_expression = var.cron
  count               = var.start_type == "cron" ? 1 : 0
}

resource "aws_cloudwatch_event_target" "lambda_schedule_rule_attachment" {
  rule  = aws_cloudwatch_event_rule.schedule_rule[0].name
  arn   = aws_lambda_function.lambda_matillion_starting.arn
  count = var.start_type == "cron" ? 1 : 0
}

resource "aws_lambda_permission" "permission_from_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda_matillion_starting.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule_rule[0].arn
  count         = var.start_type == "cron" ? 1 : 0
}
