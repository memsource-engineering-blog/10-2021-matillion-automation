import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests.exceptions import ConnectionError
from urllib3.util.retry import Retry
from urllib import request

import os
import boto3
import logging
from operator import itemgetter
import json
from sys import exit

if 'DEBUG' in os.environ:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

# Read environment variables
try:
    INSTANCE_TYPE = os.environ['INSTANCE_TYPE']
except KeyError:
    logging.critical('Cannot get INSTANCE_TYPE env variable, using default: `m5.large`.')
    INSTANCE_TYPE = 'm5.large'
logging.debug('Got INSTANCE_TYPE "%s"' % INSTANCE_TYPE)
try:
    PROJECT_VERSION = os.environ['PROJECT_VERSION']
except KeyError:
    logging.critical('Cannot get PROJECT_VERSION env variable, using default: `default`.')
    PROJECT_VERSION = 'default'
logging.debug('Got PROJECT_VERSION "%s"' % PROJECT_VERSION)
try:
    NEED_STATIC_ADDRESS = os.environ['NEED_STATIC_ADDRESS']=='true'
except KeyError:
    logging.critical('Cannot get NEED_STATIC_ADDRESS env variable, using default: `False`.')
    NEED_STATIC_ADDRESS = False
logging.debug('Got NEED_STATIC_ADDRESS "%s"' % NEED_STATIC_ADDRESS)
try:
    LAUNCH_TEMPLATE = os.environ['LAUNCH_TEMPLATE']
    PROJECT_GROUP_NAME = os.environ['PROJECT_GROUP_NAME']
    PROJECT_NAME = os.environ['PROJECT_NAME']
    JOB_NAME = os.environ['JOB_NAME']
    ENVIRONMENT_NAME = os.environ['ENVIRONMENT_NAME']
    SLACK_WEBHOOK = os.environ['SLACK_WEBHOOK']
    IMAGE_NAME_FILTER = os.environ['IMAGE_NAME_FILTER']
    GIT_BRANCH = os.environ['GIT_BRANCH']
    INSTANCE_NAME_PREFIX = os.environ['INSTANCE_NAME_PREFIX']
    SECRETS_S3_BUCKET = os.environ['SECRETS_S3_BUCKET']
except KeyError:
    logging.critical('Cannot get a required env variable.')
    exit(1)


def lambda_handler(event, context):

    username = "matillion-automation"
    password = get_password('matillion/' + username)
    job_name = f"{PROJECT_GROUP_NAME}/{PROJECT_NAME}/{PROJECT_VERSION}/{JOB_NAME}"

    instance = start_instance(job_name)
    if instance is None:
        instance = create_instance(job_name)
    address = instance.private_ip_address
    instance_id = instance.instance_id

    # Notify Slack
    slack_mentions = ":robot_face:"
    slack_message = f"instance `{instance_id}` started for automation of `{job_name}`"
    send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)

    # API call to verify that Matillion is up and running
    retry = Retry(
        total=10,
        read=10,
        connect=10,
        backoff_factor=1.2,
        status_forcelist=(111, 500, 502, 503, 504),
    )
    session = requests.Session()
    session.mount(f"http://{address}", HTTPAdapter(max_retries=retry))
    try:
        ack = session.get(f"http://{address}/rest/v1/", auth=HTTPBasicAuth(username, password))
        print(f"Received answer with length: {len(ack.text)}")
    except ConnectionError as ce:
        print(ce)
        response = instance.stop()
        instance.wait_until_stopped()
        slack_mentions = "<!channel> :rotating_light:"
        slack_message = f"instance `{instance_id}` was prematurely stopped " \
                        f"as Matillion didn't answer. " \
                        f"The automation will need to be started manually " \
                        f"for job `{job_name}`."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        exit(1)

    if pull_from_gitlab(address, username, password):
        # Run job on Matillion
        run_request = f"{build_version_url(address)}/" \
                      f"job/name/{JOB_NAME}/run?" \
                      f"environmentName={ENVIRONMENT_NAME}"
        response = requests.post(run_request, auth=HTTPBasicAuth(username, password))
        response_dict = response.json()
        if (response_dict["success"]):
            print(f"{response_dict['msg']} with TASK ID {response_dict['id']}")
            slack_mentions = ":robot_face:"
            slack_message = f"job `{job_name}` was started " \
                            f"with task id `{response_dict['id']}` " \
                            f"on instance `{instance_id}`."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        else:
            print(f"{response_dict['msg']} with TASK ID {response_dict['id']}")
            slack_mentions = "<!channel> :rotating_light:"
            slack_message = f"failed to start job `{job_name}` " \
                            f"on instance `{instance_id}`. " \
                            f"Please, check the instance manually."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
    else:
        response = instance.stop()
        instance.wait_until_stopped()
        slack_mentions = "<!channel> :rotating_light:"
        slack_message = f"instance `{instance_id}` was prematurely stopped " \
                        f"as Matillion couldn't update project from Gitlab. " \
                        f"The automation will need to be started manually " \
                        f"for job `{job_name}`."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)


def create_instance(job_name):
    # Get latest Matillion image
    ec2_client = boto3.client('ec2')
    response = ec2_client.describe_images(
        Filters=[
            {
                'Name': 'name',
                'Values': [ IMAGE_NAME_FILTER ]
            },
        ]
    )
    image_details = sorted(response['Images'],key=itemgetter('CreationDate'),reverse=True)
    image_id = image_details[0]['ImageId']

    # Run instance
    instances = ec2_client.run_instances(
        ImageId=image_id,
        InstanceType=INSTANCE_TYPE,
        MinCount=1,
        MaxCount=1,
        LaunchTemplate={
            'LaunchTemplateName': LAUNCH_TEMPLATE
        },
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': '%s-%s_%s' % (INSTANCE_NAME_PREFIX, JOB_NAME, ENVIRONMENT_NAME)
                    },
                    {
                        'Key': 'Component',
                        'Value': 'BI'
                    },
                    {
                        'Key': 'Service',
                        'Value': 'matillion'
                    },
                ]
            },
        ],
    )
    instance_id = instances['Instances'][0]['InstanceId']
    ec2 = boto3.resource('ec2')
    instance = ec2.Instance(instance_id)
    instance.wait_until_running()

    # Assign Elastic IP to Matillion instance
    if NEED_STATIC_ADDRESS:
        eip_filters = [
            {'Name': 'tag:Name', 'Values': ['matillion-automation-*']}
        ]
        response = ec2_client.describe_addresses(Filters=eip_filters)
        free_eips = [eip for eip in response["Addresses"] if "InstanceId" not in eip]
        try:
            eip = ec2.VpcAddress(free_eips[0]["AllocationId"])
            response = eip.associate(InstanceId=instance_id)
        except:
            instance.terminate()
            instance.wait_until_terminated()
            reason = "no Elastic IPs available" if len(free_eips)==0 \
                else "there was an issue while assigning the Elastic IP"
            slack_mentions = "<!channel> :rotating_light:"
            slack_message = f"instance `{instance_id}` was prematurely terminated " \
                            f"as {reason}. " \
                            f"The automation will need to be started manually " \
                            f"for job `{job_name}`."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
            exit(1)

    return instance


def start_instance(job_name):
    # Get stopped instance
    ec2_client = boto3.client('ec2')
    instance_name = '%s-%s_%s' % (INSTANCE_NAME_PREFIX, JOB_NAME, ENVIRONMENT_NAME)
    client = boto3.client('ec2')
    response = client.describe_instances(Filters=[{
        'Name':'tag:Name',
        'Values': [instance_name]}]
    )
    if (response['Reservations'] and response['Reservations'][0]['Instances']):
        instance_desc = response['Reservations'][0]['Instances'][0]
        instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
        instance_state = instance_desc['State']['Name']
        if (instance_state == 'running'):
            print('Instance already running')
            slack_mentions = "<!channel> :rotating_light:"
            slack_message = f"instance `{instance_name}` (`{instance_id}`) is already running. " \
                            f"The automation will not start the job `{job_name}`."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
            exit(1)
        if (instance_state == 'stopped'):
            response = client.start_instances(InstanceIds=[instance_id])
            ec2 = boto3.resource('ec2')
            instance = ec2.Instance(instance_id)
            instance.wait_until_running()
            return instance
        else:
            slack_mentions = ":robot_face:"
            slack_message = f"instance `{instance_name}` (`{instance_id}`) in state `{instance_state}`."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
    return None


def send_message_to_slack(webhook, slack_mentions, slack_message):
    """Sends a Slack message to a channel via an incoming webhook.

    Args:
        webhook: url of webhook to send message to Slack channel
        slack_mentions: mentioned audience
        slack_message: text of the message
    """
    slack_template = '{} Automation: {}'
    post = {"text": "{0}".format(slack_template.format(slack_mentions,
                                                       slack_message))}
    try:
        json_data = json.dumps(post)
        req = request.Request(webhook,
                              data=json_data.encode('ascii'),
                              headers={'Content-Type': 'application/json'})
        resp = request.urlopen(req)
    except Exception as e:
        print("EXCEPTION: {}".format(e))


def get_password(user):
    """Get the password for the given user from the `secrets` S3 bucket.

    Args:
        user: name of the user for which to get password
    """
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=SECRETS_S3_BUCKET, Key=user)
    password = response['Body'].read().decode('utf-8')
    return password


def build_project_url(address):
    """Build Matillion REST API URL for the project.

    Args:
        address: address of the Matillion server
    """
    return f"http://{address}/rest/v1/" \
           f"group/name/{PROJECT_GROUP_NAME}/" \
           f"project/name/{PROJECT_NAME}"


def build_version_url(address):
    """Build Matillion REST API URL for the project version.

    Args:
        address: address of the Matillion server
    """
    return f"{build_project_url(address)}/version/name/{PROJECT_VERSION}"


def pull_from_gitlab(address, username, password):
    """Switch the project version on the Matillion server to the last commit on the master branch from the Gitlab repo.

    Args:
        address: address of the Matillion server
        username: name of the Matillion user
        password: password of the Matillion user
    """
    success = False
    if call_fetch(address, username, password):
        commit_id = get_commit_id(address, username, password)
        if commit_id is None:
            slack_mentions = "<!channel> :rotating_light:"
            slack_message = "Failed to find the correct commit ID."
            send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        else:
            success = call_switch(address, username, password, commit_id)
    return success


def call_fetch(address, username, password):
    """Fetch code from the Gitlab repo.

    Args:
        address: address of the Matillion server
        username: name of the Matillion user
        password: password of the Matillion user
    """
    run_request = f"{build_project_url(address)}/scm/fetch"
    git_username = "matillion-etl"
    git_password = get_password('gitlab/' + git_username)
    payload = {
        "auth": {
            "authType": "HTTPS",
            "username": git_username,
            "password": git_password
        },
        "fetchOptions": {
        }
    }
    response = requests.post(run_request, auth=HTTPBasicAuth(username, password), json=payload)
    response_dict = response.json()
    if (response_dict["success"]):
        slack_mentions = ":robot_face:"
        slack_message = f"Project fetched from gitlab."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        return True
    else:
        slack_mentions = "<!channel> :rotating_light:"
        slack_message = f"Failed to fetch project from gitlab."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        return False


def get_commit_id(address, username, password):
    """Get ID of the last commit on the master branch.

    Args:
        address: address of the Matillion server
        username: name of the Matillion user
        password: password of the Matillion user
    """
    run_request = f"{build_project_url(address)}/scm/getState"
    response = requests.get(run_request, auth=HTTPBasicAuth(username, password))
    response_dict = response.json()
    if (response_dict["success"]):
        commit_id = find_commit(response_dict['result']['commits'])
        return commit_id
    else:
        return None


def find_commit(commits):
    for commit in commits:
        for tag in commit['tags']:
            if tag['text'] == GIT_BRANCH and (tag['type'] == "REMOTE_HEAD" or tag['type'] == "BOTH_HEAD"):
                return commit['referenceID']
    return None


def call_switch(address, username, password, commit_id):
    """Switches the project version on to the given commit.

    Args:
        address: address of the Matillion server
        username: name of the Matillion user
        password: password of the Matillion user
        commit_id: ID of the commit
    """
    run_request = f"{build_version_url(address)}/scm/switchCommit"
    payload = {
        "commitID": commit_id
    }
    response = requests.post(run_request, auth=HTTPBasicAuth(username, password), json=payload)
    response_dict = response.json()
    if response_dict["success"]:
        slack_mentions = ":robot_face:"
        slack_message = f"Switched to latest commit {commit_id}."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        return True
    else:
        slack_mentions = "<!channel> :rotating_light:"
        slack_message = f"Failed to get git commit list."
        send_message_to_slack(SLACK_WEBHOOK, slack_mentions, slack_message)
        return False
