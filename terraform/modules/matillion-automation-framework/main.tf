data "aws_vpc" "vpc" {
  tags = {
    Name = "${var.vpc_name}"
  }
}

data "aws_subnet_ids" "public_subnets" {
  vpc_id = data.aws_vpc.vpc.id

  tags = {
    Name = "public_*"
  }
}

data "aws_security_group" "matillion_sg" {
  tags = {
    Name = "matillion-security-group"
  }
}

data "aws_iam_instance_profile" "matillion_instance_profile" {
  name = "matillion-role"
}

# Elastic IPs for Matillion
resource "aws_eip" "eip" {
  vpc = true

  tags = {
    Name        = "${format("matillion-automation-%03d", count.index + 1)}"
    Component   = "BI"
    Service     = "matillion"
    Environment = "${var.environment}"
  }

  count = var.eip_count
}

# Launch template for Matillion

resource "aws_launch_template" "matillion_launch_template" {
  name = "matillion-launch-template"

  image_id                             = "ami-05b0fdaeef083dae8"
  instance_type                        = "t3.medium"
  key_name                             = var.key_name
  ebs_optimized                        = true
  instance_initiated_shutdown_behavior = "terminate"

  monitoring {
    enabled = true
  }

  iam_instance_profile {
    arn = data.aws_iam_instance_profile.matillion_instance_profile.arn
  }

  network_interfaces {
    associate_public_ip_address = true
    subnet_id                   = tolist(data.aws_subnet_ids.public_subnets.ids)[2]
    security_groups             = ["${data.aws_security_group.matillion_sg.id}"]
  }

  placement {
    availability_zone = var.availability_zone
  }

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name        = "matillion-launch-template"
      Component   = "BI"
      Service     = "matillion"
      Environment = "${var.environment}"
    }
  }

}

# Stopping Matillion

resource "aws_sqs_queue" "stopping_queue" {
  name                       = "matillion-automation-stopping"
  delay_seconds              = 90
  max_message_size           = 262144
  message_retention_seconds  = 86400
  visibility_timeout_seconds = 900 # this needs to be at least as long as
  # the timeout of the lambda function
  # which is using this queue as a trigger
}

resource "aws_lambda_function" "lambda_matillion_stopping" {
  function_name    = "matillion_automation_stopping"
  runtime          = "python3.7"
  timeout          = 900
  role             = aws_iam_role.lambda_role.arn
  handler          = "matillion_stopping_handler.lambda_handler"
  source_code_hash = filebase64sha256("${path.module}/lambda/matillion_stopping_handler.zip")
  filename         = "${path.module}/lambda/matillion_stopping_handler.zip"

  environment {
    variables = {
      "SLACK_WEBHOOK" = var.slack_hook
    }
  }
}

resource "aws_lambda_event_source_mapping" "stopping_queue_event" {
  event_source_arn = aws_sqs_queue.stopping_queue.arn
  function_name    = aws_lambda_function.lambda_matillion_stopping.arn
}

# VPC lambda configuration

resource "aws_security_group" "matillion_lambda_sg" {
  name        = "matillion-automation-lambda-security-group"
  description = "Allow lambda functions to reach Matillion"
  vpc_id      = data.aws_vpc.vpc.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "matillion-automation-lambda-security-group"
  }
}

# Role for lambdas

resource "aws_iam_role" "lambda_role" {
  name        = "matillion-automation-lambda-role"
  description = "Role for lambdas part of the Matillion automation framework"

  force_detach_policies = "true"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": ["lambda.amazonaws.com"]
      },
      "Effect": "Allow",
      "Sid": "StmAllowAssumeRole"
    }
  ]
}
EOF
}

data "aws_iam_policy" "AmazonEC2FullAccess" {
  arn = "arn:aws:iam::aws:policy/AmazonEC2FullAccess"
}

resource "aws_iam_role_policy_attachment" "AmazonEC2FullAccess-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = data.aws_iam_policy.AmazonEC2FullAccess.arn
}

data "aws_iam_policy" "AmazonSQSFullAccess" {
  arn = "arn:aws:iam::aws:policy/AmazonSQSFullAccess"
}

resource "aws_iam_role_policy_attachment" "AmazonSQSFullAccess-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = data.aws_iam_policy.AmazonSQSFullAccess.arn
}

data "aws_iam_policy" "CloudWatchLogsFullAccess" {
  arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_role_policy_attachment" "CloudWatchLogsFullAccess-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = data.aws_iam_policy.CloudWatchLogsFullAccess.arn
}

data "aws_iam_policy" "AWSLambdaVPCAccessExecutionRole" {
  arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy_attachment" "AWSLambdaVPCAccessExecutionRole-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = data.aws_iam_policy.AWSLambdaVPCAccessExecutionRole.arn
}

resource "aws_iam_policy" "passrole_policy" {
  name        = "matillion_automation_iam_passrole"
  path        = "${var.environment}/${var.region}/"
  description = "Policy to allow lambda to launch Matillion instance"

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "StmPassRole",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "*"
        }
    ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "passrole_policy-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.passrole_policy.arn
}

data "aws_iam_policy" "s3-read-access-secrets" {
  arn = var.secrets_policy_arn
  count = var.secrets_policy_arn != "" ? 1 : 0
}

resource "aws_iam_role_policy_attachment" "s3-read-access-secrets-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = data.aws_iam_policy.s3-read-access-secrets[0].arn
  count      = var.secrets_policy_arn != "" ? 1 : 0
}

resource "aws_iam_role_policy_attachment" "AWSLambdaRole-attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
}

