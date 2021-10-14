import os
import boto3
from sys import exit
import json
import ast
from urllib import request


# Read environment variables
try:
    SLACK_WEBHOOK = os.environ['SLACK_WEBHOOK']
except KeyError as e:
    logging.critical('Cannot get one of the env variables: ' + \
                     'SLACK_WEBHOOK')
    print("EXCEPTION: {}".format(e))
    exit(1)


def lambda_handler(event, context):

    for record in event['Records']:

        slack_template = '{} Automation: {}'

        # SQS message
        payload = ast.literal_eval(record["body"])
        print(payload)
        instance_id = payload["instance_id"]
        instance_name = payload["instance_name"]

        ec2 = boto3.resource('ec2')
        instance = ec2.Instance(instance_id)
        tags = instance.tags or []
        names = [tag.get('Value') for tag in tags if tag.get('Key') == 'Name']
        retrieved_name = names[0] if names else None

        if retrieved_name == instance_name \
                and 'matillion-automat' in retrieved_name:
            response = instance.stop()
            instance.wait_until_stopped()
            slack_mentions = ":robot_face:"
            slack_message = f"instance `{instance_name}`(`{instance_id}`) was stopped."
        else:
            slack_mentions = "<!channel> :rotating_light:"
            slack_message = f"instance with id `{instance_id}` and name `{instance_name}` was not found " \
                            f"or the instance is not part of automation." \
                            f"Please check running matillion instances."

        # notify slack
        send_message_to_slack(SLACK_WEBHOOK,
                              slack_template.format(slack_mentions,
                                                    slack_message))

def send_message_to_slack(webhook, text):
    """Sends a Slack message to a channel via an incoming webhook.

    Args:
        webhook: url of webhook to send message to Slack channel
        text: text of the message
    """
    post = {"text": "{0}".format(text)}
    try:
        json_data = json.dumps(post)
        req = request.Request(webhook,
                              data=json_data.encode('ascii'),
                              headers={'Content-Type': 'application/json'})
        resp = request.urlopen(req)
    except Exception as e:
        print("EXCEPTION: {}".format(e))