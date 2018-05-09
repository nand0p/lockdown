import sys
import boto3
import jinja2


iam_client = boto3.client('iam')
ec2_client = boto3.client('ec2')
sts_client = boto3.client('sts')
users = iam_client.get_account_authorization_details(Filter=['User'])['UserDetailList']
groups = iam_client.get_account_authorization_details(Filter=['Group'])['GroupDetailList']
roles = iam_client.get_account_authorization_details(Filter=['Role'])['RoleDetailList']
account_id = sts_client.get_caller_identity()['Account']
nacl_logs = []
policy_logs = []


print("Verify current user has Administrator privileges.")
user_name = iam_client.get_user()['User']['UserName']
user_policies = iam_client.list_attached_user_policies(UserName=user_name)['AttachedPolicies']
for policy in user_policies:
  if policy['PolicyName'] == "AdministratorAccess":
    user_admin = True
if user_admin:
  print("current aws profile user keys are valid.  continuing.")
else:
  print("In order to run this code, please add the AdministratorAccess managed IAM policy to your current user.")
  sys.exit(1)




if (len(sys.argv) == 1):

  print("\n\n1. Network Access Control List Deny:")
  nacls = ec2_client.describe_network_acls()['NetworkAcls']
  for nacl in nacls:
    nacl_logs.append(ec2_client.create_network_acl_entry(
      CidrBlock='0.0.0.0/0',
      Egress=True,
      Protocol='-1',
      RuleAction='deny',
      RuleNumber=1,
      NetworkAclId=nacl['NetworkAclId']
    ))
    nacl_logs.append(ec2_client.create_network_acl_entry(
      CidrBlock='0.0.0.0/0',
      Egress=False,
      Protocol='-1',
      RuleAction='deny',
      RuleNumber=2,
      NetworkAclId=nacl['NetworkAclId']
    ))
  for log in nacl_logs:
    print('Updating NACLs: ' + str(log))



  print("\n\n2. Lockdown IAM Users, Groups, and Roles")
  deny_policy = iam_client.create_policy(
    PolicyName='LockdownDenyAll',
    Description='Lockdown Deny All',
    PolicyDocument='{"Version":"2012-10-17","Statement":[{"Sid":"LockdownDenyAll","Effect":"Deny","Action":"*","Resource":"*"}]}'
  )['Policy']
  print('Create LockdownDenyAll Policy: ' + str(deny_policy))

  for user in users:
    if user['UserName'] != user_name:
      try:
        policy_logs.append(iam_client.attach_user_policy(
          UserName=user['UserName'],
          PolicyArn=deny_policy['Arn']
        ))
      except Exception as err:
        print(err)

  for group in groups:
    policy_logs.append(iam_client.attach_group_policy(
      GroupName=group['GroupName'],
      PolicyArn=deny_policy['Arn']
    ))

  for role in roles:
    if role['RoleName'] != 'AWSServiceRoleForOrganizations':
      policy_logs.append(iam_client.attach_role_policy(
        RoleName=role['RoleName'],
        PolicyArn=deny_policy['Arn']
      ))

  for log in policy_logs:
    print("Policy Attachment: " + str(log))


  print("3.  - all instances and mount volumes are snapshotted.")


  print("4.  - add bucket policy jinja template to disable all public reads and writes.")


  print("5.  - attempt to capture running processes and system memory via SSM, if available.")


  print("6.  - stop all instances.")


  print("7.  - lookup and print cloudtrail logs and vpc flowlogs location, if available.")



elif (sys.argv[1] == "revert"):

  print("1. Network Access Control List Allow.")
  nacls = ec2_client.describe_network_acls()['NetworkAcls']
  for nacl in nacls:
    try:
      nacl_logs.append(ec2_client.delete_network_acl_entry(
        Egress=True,
        RuleNumber=1,
        NetworkAclId=nacl['NetworkAclId']
      ))
    except Exception as err:
      print(err)
    try:
      nacl_logs.append(ec2_client.delete_network_acl_entry(
        Egress=False,
        RuleNumber=2,
        NetworkAclId=nacl['NetworkAclId']
      ))
    except Exception as err:
      print(err)
  for log in nacl_logs:
    print("NACL removal: " + str(log))



  print("2. Unlock IAM Users, Groups, and Roles")
  deny_policy_arn = 'arn:aws:iam::' + account_id + ':policy/LockdownDenyAll'
  print("Deny policy ARN: " + deny_policy_arn)
  for user in users:
    try:
      policy_logs.append(iam_client.detach_user_policy(
        UserName=user['UserName'],
        PolicyArn=deny_policy_arn
      ))
    except Exception as err:
      print(err)
  for group in groups:
    try:
      policy_logs.append(iam_client.detach_group_policy(
        GroupName=group['GroupName'],
        PolicyArn=deny_policy_arn
      ))
    except Exception as err:
      print(err)
  for role in roles:
    if role['RoleName'] != 'AWSServiceRoleForOrganizations':
      try:
        policy_logs.append(iam_client.detach_role_policy(
          RoleName=role['RoleName'],
          PolicyArn=deny_policy_arn
        ))
      except Exception as err:
        print(err)
  for log in policy_logs:
    print("Policy Detachment: " + str(log))

  try:
    delete_policy = iam_client.delete_policy(PolicyArn=deny_policy_arn)
    print("Delete policy: " + str(delete_policy))
  except Exception as err:
    print(err)



  print("3. Unlock S3.")
  print("  - Remove deny public access policy applied to s3 buckets is removes")
