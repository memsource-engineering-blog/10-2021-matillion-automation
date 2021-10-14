module "matillion-automation-framework" {
  source = "../../modules/matillion-automation-framework"

  key_name    = var.awx_master_key
  vpc_name    = var.vpc_name
  environment = var.environment
  region      = "eu-west-1"
  eip_count   = "1"

  slack_hook         = "https://hooks.slack.com/services/some/channel"
  secrets_policy_arn = "arn:aws:iam::my-account:policy/s3-read-access-secrets"
}
