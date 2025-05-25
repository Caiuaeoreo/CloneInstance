#!/usr/bin/env python3
import boto3
import sys
from datetime import datetime

def clone_instance_with_new_ami(instance_id, new_ami_id, profile, new_name, source_region, target_region=None):
    # Usaa mesma região se não passar a target
    if target_region is None:
        target_region = source_region
    
    print(f"Starting to clone instance {instance_id} from {source_region} with new AMI {new_ami_id}" + 
          (f" to {target_region}" if target_region != source_region else "") + "...")

    # Definindo profile
    session = boto3.Session(profile_name=profile)
    
    # Definindo as variaveis de para não ter que escrever a chamada do boto toda a hora 
    source_ec2 = session.client('ec2', region_name=source_region)
    target_ec2 = session.client('ec2', region_name=target_region)
    
    # Pegando dados da intância base
    response = source_ec2.describe_instances(InstanceIds=[instance_id])

    # Se der erro aqui é pq ele não encontrou a instância nessa região
    if not response['Reservations'] or not response['Reservations'][0]['Instances']:
        print(f"Error: Instance {instance_id} not found in {source_region}")
        sys.exit(1)

    # Para a instância para fazer o clone
    source_ec2.stop_instances(InstanceIds=[instance_id])
    
    # Get dos dados da instância (Melhor para gerenciar o json)    
    instance = response['Reservations'][0]['Instances'][0]
    
    # Verifica a existencia da AMI
    try:
        ami_check = target_ec2.describe_images(ImageIds=[new_ami_id])
        if not ami_check['Images']:
            print(f"Error: AMI {new_ami_id} not found in {target_region}")
            sys.exit(1)
    except Exception as e:
        print(f"Error: AMI {new_ami_id} not found in {target_region} or not accessible: {e}")
        sys.exit(1)
    
    # Parametros para criação da nova máquina.
    run_params = {
        'ImageId': new_ami_id,
        'InstanceType': instance['InstanceType'],
        'MaxCount': 1,
        'MinCount': 1
    }
    
    # Add subnet se existir - Precisa ser alterado para melhor ganularidade caso seja usado apra regiões diferentes
    if 'SubnetId' in instance:
        if source_region == target_region:
            # Pega a AZ atual da máquina que vai ser clonada
            source_az = instance['Placement'].get('AvailabilityZone')
            
            # pega todas as AZs da região
            azs = target_ec2.describe_availability_zones(
                Filters=[{'Name': 'region-name', 'Values': [target_region]}]
            )['AvailabilityZones']
            
            '''
            Vou explicar aqui para quem quiser saber pq achei fantastico essa forma de preencher a lista.
            Resumindo, leia a linha abaixo como se fosse uma abstração disso:
            available_azs = []
            for az in azs:
                if az['State'] == 'available':
                    available_azs.append(az['ZoneName'])
            
            Entendeu? rlx, minha mente também fez blow mind quando entendi como funciona kkk

            link de referencia: https://www.w3schools.com/python/python_lists_comprehension.asp
            '''
            available_azs = [az['ZoneName'] for az in azs if az['State'] == 'available']
            
            if len(available_azs) > 1 and source_az:
                # Remove a source az da lista de azs disponiveis
                if source_az in available_azs:
                    available_azs.remove(source_az)
                
                # usa a primeira az disponivel das que sobraram
                target_az = available_azs[0]
                
                # Pega todas as subnets
                subnets = target_ec2.describe_subnets()['Subnets']
                target_subnet = None
                
                # Pega a subnet usada para a instância raiz e a VPC para o if
                source_subnet = target_ec2.describe_subnets(SubnetIds=[instance['SubnetId']])['Subnets'][0]
                source_vpc = source_subnet['VpcId']
                
                # Filtra as subnets que atendem aos critérios
                matching_subnets = [
                    subnet for subnet in subnets
                    #if subnet['AvailabilityZone'] == target_az and subnet['VpcId'] == source_vpc
                    if subnet['VpcId'] == source_vpc
                ]

                # Se houver subnets compatíveis, exibe e pede escolha
                if matching_subnets:
                    print("Subnets disponíveis:")
                    for id, subnet in enumerate(matching_subnets, start=1):
                        name = next(
                            (tag['Value'] for tag in subnet.get('Tags', []) if tag['Key'] == 'Name'),
                            'Sem nome'
                        )
                        print(f"{id} - {subnet['SubnetId']} | {name}")

                    # Solicita ao user que escolha uma subnet
                    while True:
                        try:
                            choice = int(input("Escolha o número da subnet desejada: "))
                            if 1 <= choice <= len(matching_subnets):
                                target_subnet = matching_subnets[choice - 1]['SubnetId']
                                break
                            else:
                                print("Número inválido. Tente novamente.")
                        except ValueError:
                            print("Entrada inválida. Digite um número.")
                else:
                    # Se não houver subnets compatíveis, usa a original
                    target_subnet = instance['SubnetId']
                    print("Aviso: Nenhuma subnet encontrada na AZ alvo. Usando a subnet original.")

                # Define o parâmetro de execução
                run_params['SubnetId'] = target_subnet
                print(f"Usando subnet {target_subnet}")

            else:
                # Se houver apenas uma AZ disponivel, usa a mesma subnet
                run_params['SubnetId'] = instance['SubnetId']
        else:
            # Para cross, temos que buscar uma subnet analoga
            source_az = instance['Placement']['AvailabilityZone']
            source_az_letter = source_az[-1]  # pega a letra da AZ (a, b, c e etc..)
            
            try:
                # Pega todas as subnets na target region
                subnets = target_ec2.describe_subnets()['Subnets']
                
                # Tenta encontrar a subnet na mesma letra final da AZ
                target_subnet = None
                for subnet in subnets:
                    target_az = subnet['AvailabilityZone']
                    if target_az[-1] == source_az_letter:
                        target_subnet = subnet['SubnetId']
                        break
                
                # Se nenhuma subnet for encontrada na mesma AZ, escolher a primeira da lista
                if not target_subnet and subnets:
                    target_subnet = subnets[0]['SubnetId']
                
                if target_subnet:
                    run_params['SubnetId'] = target_subnet
                    print(f"Using subnet {target_subnet} in target region {target_region}")
                else:
                    print(f"Warning: No subnet found in target region {target_region}. Instance will be launched in default subnet.")
            except Exception as e:
                print(f"Warning: Error finding subnet in target region: {e}. Instance will be launched in default subnet.")
    
    # Add security group se existir - precisa alterar se for usar cross region
    if 'SecurityGroups' in instance:
        if source_region == target_region:
            run_params['SecurityGroupIds'] = [sg['GroupId'] for sg in instance['SecurityGroups']]
        else:

            print("Warning: Cross-region cloning - using default security group in target region")
            try:
                vpcs = target_ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])
                if vpcs['Vpcs']:
                    default_vpc_id = vpcs['Vpcs'][0]['VpcId']
                    
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
    
    # Adiciona a keypair se existir - precisa validar o cross
    if 'KeyName' in instance:
        key_name = instance['KeyName']
        if source_region == target_region:
            run_params['KeyName'] = key_name
        else:
            try:
                key_pairs = target_ec2.describe_key_pairs(KeyNames=[key_name])
                run_params['KeyName'] = key_name
            except:
                print(f"Warning: Key pair '{key_name}' not found in target region {target_region}. Instance will be launched without key pair.")
    
    # Add user data se existir
    if 'UserData' in instance:
        run_params['UserData'] = instance['UserData']
    
    # Add IAM instance profile se existir
    if 'IamInstanceProfile' in instance:
        profile_name = instance['IamInstanceProfile']['Arn'].split('/')[-1]
        run_params['IamInstanceProfile'] = {'Name': profile_name}
    
    # Add metadata options se existir
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
    
    # Add monitoring if habilitado
    if 'Monitoring' in instance and instance['Monitoring']['State'] == 'enabled':
        run_params['Monitoring'] = {'Enabled': True}
    
    # Add EBS optimized se habilitado
    if 'EbsOptimized' in instance and instance['EbsOptimized']:
        run_params['EbsOptimized'] = True
    
    # Add placement information se existir
    if 'Placement' in instance:
        placement = {}
        if 'Tenancy' in instance['Placement'] and instance['Placement']['Tenancy'] != 'default':
            placement['Tenancy'] = instance['Placement']['Tenancy']
        
        # Para cross region tem que mexer
        if source_region == target_region:
            # Pegando a source az
            source_az = instance['Placement'].get('AvailabilityZone')
            if source_az:
                # Pega todas as AZs da region
                azs = target_ec2.describe_availability_zones(
                    Filters=[{'Name': 'region-name', 'Values': [target_region]}]
                )['AvailabilityZones']
                
                available_azs = [az['ZoneName'] for az in azs if az['State'] == 'available']
                
                if len(available_azs) > 1:
                    # Remove a source az das disponiveis (objetivoo é a diferente)
                    if source_az in available_azs:
                        available_azs.remove(source_az)
                    
                    # Usa a primeira disponivel da lista
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
    apply_tags(source_ec2, target_ec2, profile, instance_id, new_instance_id, new_name)
    
    print(f"Cloning completed! New instance ID: {new_instance_id} in region {target_region}")
    return new_instance_id

def apply_tags(source_ec2, target_ec2, profile, source_instance_id, target_instance_id, new_name=None):
    print("Copying tags from original instance...")
    tags_response = source_ec2.describe_tags(
        Filters=[{'Name': 'resource-id', 'Values': [source_instance_id]}]
    )
    
    # Pega o mes e ano atual
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    if tags_response['Tags']:
        tags_to_apply = []
        original_name = None
        
        # First, find the original Name tag if it exists
        for tag in tags_response['Tags']:

            if tag['Key'].startswith('aws:'):
                continue

            if tag['Key'] == 'Name':
                original_name = tag['Value']
                break
        
        for tag in tags_response['Tags']:
            if tag['Key'] == 'Name':
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
        
        if not original_name and new_name:
            tags_to_apply.append({
                'Key': 'Name',
                'Value': f"{new_name}-DR-{current_date}"
            })
        
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
