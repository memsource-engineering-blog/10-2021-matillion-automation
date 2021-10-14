variable "instance_type" {
  type        = string
  description = "The type of instance to use for Matillion"
  default     = "t3.medium"
}

variable "matillion_project_group_name" {
  type        = string
  description = "The name of the project group where the job to automate is saved"
}

variable "matillion_project_name" {
  type        = string
  description = "The name of the project where the job to automate is saved"
}

variable "matillion_job_name" {
  type        = string
  description = "The name of the job to automate"
}

variable "matillion_project_git_branch" {
  type        = string
  description = "The name of the Gitlab branch with the job version to be used"
  default     = "master"
}

variable "matillion_environment_name" {
  type        = string
  description = "The name of the environment where to run the job"
}

variable "start_type" {
  type        = string
  description = "Variable define how to start automation - cron or trigger via SQS message. Possible values are 'cron', 'trigger'."
  default     = "cron"
}

variable "cron" {
  type        = string
  description = "The schedule for the automation to run (without seconds), for example `cron(10 15 * * ? *)`. Note that it is GMT time."
  default     = ""
}

variable "queue_env" {
  type        = string
  description = "Queue environment, eg. 'production'"
  default     = ""
}

variable "launch_template_name" {
  type        = string
  description = "The name of the launch template to use for the instance"
  default     = "matillion-launch-template"
}

variable "vpc_name" {
  type        = string
  description = "Name of VPC to deploy into"
}

variable "slack_webhook" {
  type        = string
  description = "Hook to write to Slack"
  default     = ""
}

variable "image_name_filter" {
  type        = string
  description = "Filter to apply to retrieve Matillion image to use for automation"
}

variable "need_static_address" {
  type        = bool
  description = "Whether the Matillion instance needs a static address - to access ElasticSearch."
  default     = false
}

variable "slack_alert_webhook" {
  type        = string
  description = "Hook to write important alerts to Slack"
  default     = ""
}

variable "safeguard_cron" {
  type        = string
  description = "The schedule for the safeguard check to run (without seconds), for example `cron(10 15 * * ? *)`. Note that it is GMT time."
  default     = ""
}

variable "lambda_name_prefix" {
  type        = string
  description = "The prefix to be used for names of lambdas and event rules."
  default     = "matillion"
}

variable "instance_name_prefix" {
  type        = string
  description = "The prefix to be used for names of lambdas and event rules."
  default     = "matillion-automation"
}

variable "secrets_s3_bucket" {
  type        = string
  description = "Name of the S3 bucket containing secrets"
}

