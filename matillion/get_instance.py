import requests
import boto3

r = requests.get("http://169.254.169.254/latest/dynamic/instance-identity/document")
response_json = r.json()
region = response_json.get('region')
instance_id = response_json.get('instanceId')

ec2 = boto3.resource('ec2', region_name=region)
instance = ec2.Instance(instance_id)

tags = instance.tags or []
names = [tag.get('Value') for tag in tags if tag.get('Key') == 'Name']
name = names[0] if names else None

context.updateVariable('v_instance_id', instance_id)
context.updateVariable('v_instance_name', name)

print("Instance id: " + v_instance_id)
print("Instance name: " + v_instance_name)