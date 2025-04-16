#!/usr/bin/env python3
import boto3
import sys
from datetime import datetime

def clone_instance_with_new_ami(instance_id, new_ami_id, new_name, source_region, target_region=None):
    """
    Clone an EC2 instance with a new AMI while preserving all other settings
    
    Args:
        instance_id (str): ID of the instance to clone
        new_ami_id (str): ID of the new AMI to use
        new_name (str, optional): New name for the instance
        source_region (str): AWS region where the source instance is located
        target_region (str, optional): AWS region where to create the new instance.
                                      If None, uses the same region as source.
    """
    # If target_region is not specified, use the same as source_region
    if target_region is None:
        target_region = source_region
    
    print(f"Starting to clone instance {instance_id} from {source_region} with new AMI {new_ami_id}" + 
          (f" to {target_region}" if target_region != source_region else "") + "...")
    
    # Initialize boto3 clients
    source_ec2 = boto3.client('ec2', region_name=source_region)
    target_ec2 = boto3.client('ec2', region_name=target_region)
    
    # Get instance details
    response = source_ec2.describe_instances(InstanceIds=[instance_id])
    if not response['Reservations'] or not response['Reservations'][0]['Instances']:
        print(f"Error: Instance {instance_id} not found in {source_region}")
        sys.exit(1)

    source_ec2.stop_instances(InstanceIds=[instance_id])
        
    instance = response['Reservations'][0]['Instances'][0]
    
    # Check if AMI exists in target region
    try:
        ami_check = target_ec2.describe_images(ImageIds=[new_ami_id])
        if not ami_check['Images']:
            print(f"Error: AMI {new_ami_id} not found in {target_region}")
            sys.exit(1)
    except Exception as e:
        print(f"Error: AMI {new_ami_id} not found in {target_region} or not accessible: {e}")
        sys.exit(1)
    
    # Prepare run_instances parameters
    run_params = {
        'ImageId': new_ami_id,
        'InstanceType': instance['InstanceType'],
        'MaxCount': 1,
        'MinCount': 1
    }
    
    # Add subnet if exists - need to handle cross-region case and different AZ
    if 'SubnetId' in instance:
        if source_region == target_region:
            # Get the source AZ
            source_az = instance['Placement'].get('AvailabilityZone')
            
            # Get all AZs in the region
            azs = target_ec2.describe_availability_zones(
                Filters=[{'Name': 'region-name', 'Values': [target_region]}]
            )['AvailabilityZones']
            
            available_azs = [az['ZoneName'] for az in azs if az['State'] == 'available']
            
            if len(available_azs) > 1 and source_az:
                # Remove the source AZ from the list of available AZs
                if source_az in available_azs:
                    available_azs.remove(source_az)
                
                # Use the first available AZ that's different from the source
                target_az = available_azs[0]
                
                # Find a subnet in the target AZ
                subnets = target_ec2.describe_subnets()['Subnets']
                target_subnet = None
                
                # Try to find a subnet in the same VPC as the source subnet
                source_subnet = target_ec2.describe_subnets(SubnetIds=[instance['SubnetId']])['Subnets'][0]
                source_vpc = source_subnet['VpcId']
                
                for subnet in subnets:
                    if subnet['AvailabilityZone'] == target_az and subnet['VpcId'] == source_vpc:
                        target_subnet = subnet['SubnetId']
                        break
                
                if target_subnet:
                    run_params['SubnetId'] = target_subnet
                    print(f"Using subnet {target_subnet} in AZ {target_az} (original was in {source_az})")
                else:
                    # If no subnet found in target AZ with same VPC, use original subnet
                    run_params['SubnetId'] = instance['SubnetId']
                    print(f"Warning: Could not find a subnet in a different AZ. Using original subnet.")
            else:
                # If only one AZ available or source AZ not found, use original subnet
                run_params['SubnetId'] = instance['SubnetId']
        else:
            # For cross-region, we need to find a suitable subnet in the target region
            # We'll use the first subnet in the same AZ letter (if possible)
            source_az = instance['Placement']['AvailabilityZone']
            source_az_letter = source_az[-1]  # Get the AZ letter (a, b, c, etc.)
            
            try:
                # Get all subnets in target region
                subnets = target_ec2.describe_subnets()['Subnets']
                
                # Try to find a subnet in the same AZ letter
                target_subnet = None
                for subnet in subnets:
                    target_az = subnet['AvailabilityZone']
                    if target_az[-1] == source_az_letter:
                        target_subnet = subnet['SubnetId']
                        break
                
                # If no subnet found with same AZ letter, use the first one
                if not target_subnet and subnets:
                    target_subnet = subnets[0]['SubnetId']
                
                if target_subnet:
                    run_params['SubnetId'] = target_subnet
                    print(f"Using subnet {target_subnet} in target region {target_region}")
                else:
                    print(f"Warning: No subnet found in target region {target_region}. Instance will be launched in default subnet.")
            except Exception as e:
                print(f"Warning: Error finding subnet in target region: {e}. Instance will be launched in default subnet.")
    
    # Add security groups if exist - need to handle cross-region case
    if 'SecurityGroups' in instance:
        if source_region == target_region:
            run_params['SecurityGroupIds'] = [sg['GroupId'] for sg in instance['SecurityGroups']]
        else:
            # For cross-region, we need to find or create equivalent security groups
            # For simplicity, we'll use the default security group
            print("Warning: Cross-region cloning - using default security group in target region")
            try:
                # Get default VPC
                vpcs = target_ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
                if vpcs['Vpcs']:
                    default_vpc_id = vpcs['Vpcs'][0]['VpcId']
                    
                    # Get default security group
                    sgs = target_ec2.describe_security_groups(
                        Filters=[
                            {'Name': 'vpc-id', 'Values': [default_vpc_id]},
                            {'Name': 'group-name', 'Values': ['default']}
                        ]
                    )
                    if sgs['SecurityGroups']:
                        run_params['SecurityGroupIds'] = [sgs['SecurityGroups'][0]['GroupId']]
            except Exception as e:
                print(f"Warning: Error finding default security group: {e}")
    
    # Add key name if exists - need to check if key exists in target region
    if 'KeyName' in instance:
        key_name = instance['KeyName']
        if source_region == target_region:
            run_params['KeyName'] = key_name
        else:
            # Check if the key exists in target region
            try:
                key_pairs = target_ec2.describe_key_pairs(KeyNames=[key_name])
                run_params['KeyName'] = key_name
            except:
                print(f"Warning: Key pair '{key_name}' not found in target region {target_region}. Instance will be launched without key pair.")
    
    # Add user data if exists
    if 'UserData' in instance:
        run_params['UserData'] = instance['UserData']
    
    # Add IAM instance profile if exists
    if 'IamInstanceProfile' in instance:
        profile_name = instance['IamInstanceProfile']['Arn'].split('/')[-1]
        run_params['IamInstanceProfile'] = {'Name': profile_name}
    
    # Add metadata options if exist
    if 'MetadataOptions' in instance:
        metadata_options = {}
        if 'HttpEndpoint' in instance['MetadataOptions']:
            metadata_options['HttpEndpoint'] = instance['MetadataOptions']['HttpEndpoint']
        if 'HttpTokens' in instance['MetadataOptions']:
            metadata_options['HttpTokens'] = instance['MetadataOptions']['HttpTokens']
        if 'HttpPutResponseHopLimit' in instance['MetadataOptions']:
            metadata_options['HttpPutResponseHopLimit'] = instance['MetadataOptions']['HttpPutResponseHopLimit']
        
        if metadata_options:
            run_params['MetadataOptions'] = metadata_options
    
    # Add monitoring if enabled
    if 'Monitoring' in instance and instance['Monitoring']['State'] == 'enabled':
        run_params['Monitoring'] = {'Enabled': True}
    
    # Add EBS optimized if enabled
    if 'EbsOptimized' in instance and instance['EbsOptimized']:
        run_params['EbsOptimized'] = True
    
    # Add placement information if exists
    if 'Placement' in instance:
        placement = {}
        if 'Tenancy' in instance['Placement'] and instance['Placement']['Tenancy'] != 'default':
            placement['Tenancy'] = instance['Placement']['Tenancy']
        
        # For cross-region, we can't specify the same AZ
        if source_region == target_region:
            # Get the source AZ
            source_az = instance['Placement'].get('AvailabilityZone')
            if source_az:
                # Get all AZs in the region
                azs = target_ec2.describe_availability_zones(
                    Filters=[{'Name': 'region-name', 'Values': [target_region]}]
                )['AvailabilityZones']
                
                available_azs = [az['ZoneName'] for az in azs if az['State'] == 'available']
                
                if len(available_azs) > 1:
                    # Remove the source AZ from the list of available AZs
                    if source_az in available_azs:
                        available_azs.remove(source_az)
                    
                    # Use the first available AZ that's different from the source
                    target_az = available_azs[0]
                    placement['AvailabilityZone'] = target_az
                    print(f"Placing new instance in a different AZ: {target_az} (original was {source_az})")
        
        if placement:
            run_params['Placement'] = placement
    
    # Add credit specification for T instances
    if instance['InstanceType'].startswith('t') and 'CreditSpecification' in instance:
        if 'CpuCredits' in instance['CreditSpecification']:
            run_params['CreditSpecification'] = {
                'CpuCredits': instance['CreditSpecification']['CpuCredits']
            }
    
    # Add hibernation options if enabled
    if 'HibernationOptions' in instance and instance['HibernationOptions']['Configured']:
        run_params['HibernationOptions'] = {'Configured': True}
    
    # Add enclave options if enabled
    if 'EnclaveOptions' in instance and instance['EnclaveOptions']['Enabled']:
        run_params['EnclaveOptions'] = {'Enabled': True}
    
    # Handle block device mappings for non-root volumes
    if 'BlockDeviceMappings' in instance:
        root_device = instance['RootDeviceName']
        block_device_mappings = []
        
        for bdm in instance['BlockDeviceMappings']:
            # Skip root device as it will be replaced by the new AMI
            if bdm['DeviceName'] == root_device:
                continue
                
            if 'Ebs' in bdm:
                volume_id = bdm['Ebs']['VolumeId']
                volume = source_ec2.describe_volumes(VolumeIds=[volume_id])['Volumes'][0]
                
                new_bdm = {
                    'DeviceName': bdm['DeviceName'],
                    'Ebs': {
                        'VolumeSize': volume['Size'],
                        'VolumeType': volume['VolumeType'],
                        'DeleteOnTermination': bdm['Ebs'].get('DeleteOnTermination', False),
                        'Encrypted': volume['Encrypted']
                    }
                }
                
                # Add IOPS if applicable
                if 'Iops' in volume:
                    new_bdm['Ebs']['Iops'] = volume['Iops']
                
                # Add Throughput if applicable (for gp3)
                if 'Throughput' in volume:
                    new_bdm['Ebs']['Throughput'] = volume['Throughput']
                
                block_device_mappings.append(new_bdm)
        
        if block_device_mappings:
            run_params['BlockDeviceMappings'] = block_device_mappings
    
    # Launch the new instance
    print(f"Creating new instance in {target_region}...")
    response = target_ec2.run_instances(**run_params)
    new_instance_id = response['Instances'][0]['InstanceId']
    print(f"New instance created with ID: {new_instance_id}")
    
    # Apply tags to the new instance
    apply_tags(source_ec2, target_ec2, instance_id, new_instance_id, new_name)
    
    print(f"Cloning completed! New instance ID: {new_instance_id} in region {target_region}")
    return new_instance_id

def apply_tags(source_ec2, target_ec2, source_instance_id, target_instance_id, new_name=None):
    """
    Copy tags from source instance to target instance, with special handling for Name tag
    
    Args:
        source_ec2: boto3 EC2 client for source region
        target_ec2: boto3 EC2 client for target region
        source_instance_id (str): ID of the source instance
        target_instance_id (str): ID of the target instance
        new_name (str, optional): New name for the instance
    """
    print("Copying tags from original instance...")
    tags_response = source_ec2.describe_tags(
        Filters=[{'Name': 'resource-id', 'Values': [source_instance_id]}]
    )
    
    # Get current month/year for the name suffix
    current_date = datetime.now().strftime("%m/%Y")
    
    if tags_response['Tags']:
        tags_to_apply = []
        original_name = None
        
        # First, find the original Name tag if it exists
        for tag in tags_response['Tags']:
            if tag['Key'] == 'Name':
                original_name = tag['Value']
                break
        
        # Now create all tags, with special handling for the Name tag
        for tag in tags_response['Tags']:
            if tag['Key'] == 'Name':
                # If new_name is provided, use it; otherwise format the original name
                if new_name:
                    name_value = f"{new_name}-DR-{current_date}"
                else:
                    name_value = f"{original_name}-DR-{current_date}" if original_name else f"Instance-DR-{current_date}"
                
                tags_to_apply.append({
                    'Key': 'Name',
                    'Value': name_value
                })
            else:
                tags_to_apply.append({
                    'Key': tag['Key'],
                    'Value': tag['Value']
                })
        
        # If there was no Name tag but new_name is provided, add it
        if not original_name and new_name:
            tags_to_apply.append({
                'Key': 'Name',
                'Value': f"{new_name}-DR-{current_date}"
            })
        
        # Add source instance ID and region as tags
        tags_to_apply.append({
            'Key': 'SourceInstanceId',
            'Value': source_instance_id
        })
        
        source_region = source_ec2.meta.region_name
        tags_to_apply.append({
            'Key': 'SourceRegion',
            'Value': source_region
        })
        
        target_ec2.create_tags(
            Resources=[target_instance_id],
            Tags=tags_to_apply
        )
