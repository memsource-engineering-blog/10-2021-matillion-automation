This module creates all the necessary resources 
for automation of Matillion jobs.

## Assumptions
We assume that a Matillion instance already exists.
We also assume that a security group for Matillion and 
an instance IAM profile exist.

## Elastic IPs
We generally assign Elastic IPs to Matillion instances 
to make it easier to allow Matillion access to 
source and sink systems.

## Roles
All necessary roles are created for allowing Lambdas to
* start and stop the Matillion EC2 instance
* read secrets from S3 bucket (e.g., for git authentication)
* read and write SQS

**Note:** sometimes, full access is granted, for simplicity.
  A stricter set of permissions is also possible.

## Stopping Lambda and SQS
An SQS queue and a Lambda function are created 
to be able to coordinate the stopping of Matillion instance
upon completion of a job.