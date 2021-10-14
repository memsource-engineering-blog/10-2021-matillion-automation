provider "aws" {
  region              = "eu-west-1"
  allowed_account_ids = ["my-account"]
}

terraform {
  backend "s3" {
    bucket         = "terraform-state.my-bucket.com"
    dynamodb_table = "terraform-state-lock"
    key            = "state/matillion-automation-framework"
    region         = "eu-west-1"
  }
}
