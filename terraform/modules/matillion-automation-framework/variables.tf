variable "environment" {
  type        = string
  description = "Environment for the lambda role"
}

variable "region" {
  type        = string
  description = "Region which is used to create the lambda role"
}

variable "vpc_name" {
  type        = string
  description = "Name of VPC to deploy into"
}

variable "availability_zone" {
  type        = string
  description = "Availability zone to deploy into"
  default     = "eu-west-1a"
}

variable "key_name" {
  type        = string
  description = "Name of key to put into key_name for instance"
}

variable "eip_count" {
  type        = number
  description = "Number of Elastic IPs to reserve for Matillion"
}

variable "slack_hook" {
  type        = string
  description = "Slack webhook for notifications"
}

variable "secrets_policy_arn" {
  type        = string
  description = "ARN of the policy giving access to the secrets"
  default     = ""
}