#!/usr/bin/env python3
import boto3
import sys
from datetime import datetime

# Importa as funções de volume do novo módulo
try:
    from libs.ec2_volume_utils import prepare_root_volume_mapping, add_block_device_mappings
except ImportError:
    # Se o módulo não estiver disponível, usa as funções locais
    pass

def clone_instance_with_new_ami(instance_id, new_ami_id, profile, new_name, source_region, target_region=None):
    """
    Função principal que coordena todo o processo de clonagem da instância
    """
    # Captura o horário de início
    start_time = datetime.now().strftime("%H:%M")
    
    # Usaa mesma região se não passar a target
    if target_region is None:
        target_region = source_region
    
    # Verificamos se estamos tentando clonar para outra região
    if target_region != source_region:
        print("ERRO: A clonagem entre regiões foi descontinuada. Use a mesma região de origem e destino.")
        sys.exit(1)
    
    print(f"\n🔄 Iniciando clonagem da instância {instance_id} com a nova AMI {new_ami_id}...\n")

    # Definindo profile
    session = boto3.Session(profile_name=profile)
    
    # Definindo as variaveis de para não ter que escrever a chamada do boto toda a hora 
    ec2_client = session.client('ec2', region_name=source_region)
    
    # Pega os dados da instância de origem
    print("📋 Obtendo informações da instância de origem...")
    instance = get_instance_data(ec2_client, instance_id)
    
    # Verifica se a AMI existe na região
    print("🔍 Verificando se a AMI existe...")
    verify_ami_exists(ec2_client, new_ami_id, source_region)
    
    # Para a instância para fazer o clone
    print(f"⏸️  Parando a instância {instance_id} antes da clonagem...")
    stop_source_instance(ec2_client, instance_id)
    
    # Prepara os parâmetros para criar a nova instância
    print("⚙️  Preparando configurações para a nova instância...")
    run_params = prepare_run_params(instance, new_ami_id, ec2_client)
    
    # Cria a nova instância
    print("🚀 Criando nova instância...")
    response = ec2_client.run_instances(**run_params)
    new_instance_id = response['Instances'][0]['InstanceId']
    print(f"✅ Nova instância criada com ID: {new_instance_id}")
    
    # Aplica as tags na nova instância
    print("🏷️  Aplicando tags na nova instância...")
    apply_tags(ec2_client, instance_id, new_instance_id, new_name)
    
    print(f"\n✨ Clonagem concluída com sucesso! ✨")
    print(f"📌 Nova instância ID: {new_instance_id}")
    print(f"📌 Tipo: {instance['InstanceType']}")
    
    # Obtém o nome da nova instância para exibir
    tags_response = ec2_client.describe_tags(
        Filters=[
            {'Name': 'resource-id', 'Values': [new_instance_id]},
            {'Name': 'key', 'Values': ['Name']}
        ]
    )
    
    if tags_response['Tags']:
        instance_name = tags_response['Tags'][0]['Value']
        print(f"📌 Nome: {instance_name}")
    
    # Aguarda a instância iniciar
    print("\n⏳ Aguardando a nova instância inicializar...")
    waiter = ec2_client.get_waiter('instance_running')
    waiter.wait(InstanceIds=[new_instance_id])
    print("✅ Nova instância está em execução e pronta para uso!")
    
    # Captura o horário de fim
    end_time = datetime.now().strftime("%H:%M")
    
    # Gera relatório final detalhado
    generate_final_report(ec2_client, instance_id, new_instance_id, instance, profile, start_time, end_time)
    
    return new_instance_id

def get_instance_data(ec2_client, instance_id):
    """
    Pega os dados da instância de origem
    """
    response = ec2_client.describe_instances(InstanceIds=[instance_id])

    # Se der erro aqui é pq ele não encontrou a instância nessa região
    if not response['Reservations'] or not response['Reservations'][0]['Instances']:
        print(f"❌ ERRO: Instância {instance_id} não encontrada")
        sys.exit(1)
        
    return response['Reservations'][0]['Instances'][0]

def verify_ami_exists(ec2_client, ami_id, region):
    """
    Verifica se a AMI existe na região especificada
    """
    try:
        ami_check = ec2_client.describe_images(ImageIds=[ami_id])
        if not ami_check['Images']:
            print(f"❌ ERRO: AMI {ami_id} não encontrada")
            sys.exit(1)
    except Exception as e:
        print(f"❌ ERRO: AMI {ami_id} não encontrada ou não acessível: {e}")
        sys.exit(1)
        
def generate_final_report(ec2_client, source_instance_id, target_instance_id, source_instance, profile, start_time, end_time):
    """
    Gera um relatório final detalhado da clonagem
    """
    # Obtém informações da nova instância
    target_response = ec2_client.describe_instances(InstanceIds=[target_instance_id])
    target_instance = target_response['Reservations'][0]['Instances'][0]
    
    # Obtém nomes das instâncias
    source_name = "Sem nome"
    target_name = "Sem nome"
    
    # Busca nome da instância de origem
    source_tags = ec2_client.describe_tags(
        Filters=[
            {'Name': 'resource-id', 'Values': [source_instance_id]},
            {'Name': 'key', 'Values': ['Name']}
        ]
    )
    if source_tags['Tags']:
        source_name = source_tags['Tags'][0]['Value']
    
    # Busca nome da instância de destino
    target_tags = ec2_client.describe_tags(
        Filters=[
            {'Name': 'resource-id', 'Values': [target_instance_id]},
            {'Name': 'key', 'Values': ['Name']}
        ]
    )
    if target_tags['Tags']:
        target_name = target_tags['Tags'][0]['Value']
    
    # Obtém informações de rede
    source_subnet_id = source_instance.get('SubnetId', 'N/A')
    target_subnet_id = target_instance.get('SubnetId', 'N/A')
    
    source_az = source_instance['Placement'].get('AvailabilityZone', 'N/A')
    target_az = target_instance['Placement'].get('AvailabilityZone', 'N/A')
    
    source_private_ip = source_instance.get('PrivateIpAddress', 'N/A')
    target_private_ip = target_instance.get('PrivateIpAddress', 'N/A')
    
    # Obtém AMI ID
    target_ami_id = target_instance['ImageId']
    
    # Obtém a data atual
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    # Gera o relatório
    print("\n\n" + "="*50)
    print("===Consigcard===\n")
    print(f"Account: {profile.upper()}\n")
    print(f"Aplicação: \n")
    print(f"EC2: {target_name} - {target_instance_id}")
    print(f"AMI: {target_ami_id}")
    print(f"(A original era {source_instance_id})")
    print(f"AZ: {target_az} (original era {source_az})")
    print(f"Sub: {target_subnet_id} (original era {source_subnet_id})\n")
    print(f"Removida do LB: ")
    print(f"Voltou ao LB: ")
    print(f"Inicio: {start_time}")
    print(f"Fim: {end_time}\n")
    print(f"Novo IP: {target_private_ip} (original era {source_private_ip})")
    print("\n" + "="*50)
    
    # Salva o relatório em um arquivo
    report_filename = f"clone_report_{target_instance_id}_{current_date.replace('/', '-')}.txt"
    try:
        with open(report_filename, 'w') as f:
            f.write("===Consigcard===\n\n")
            f.write(f"Account: {profile.upper()}\n\n")
            f.write(f"Aplicação: \n\n")
            f.write(f"EC2: {target_name} - {target_instance_id}\n")
            f.write(f"AMI: {target_ami_id}\n")
            f.write(f"(A original era {source_instance_id})\n")
            f.write(f"AZ: {target_az} (original era {source_az})\n")
            f.write(f"Sub: {target_subnet_id} (original era {source_subnet_id})\n\n")
            f.write(f"Removida do LB: \n")
            f.write(f"Voltou ao LB: \n")
            f.write(f"Inicio: {start_time}\n")
            f.write(f"Fim: {end_time}\n\n")
            f.write(f"Novo IP: {target_private_ip} (original era {source_private_ip})\n")
        
        print(f"\nRelatório salvo em: {report_filename}")
    except Exception as e:
        print(f"Não foi possível salvar o relatório em arquivo: {e}")
        print("Copie as informações acima manualmente.")

def stop_source_instance(ec2_client, instance_id):
    """
    Para a instância de origem antes de fazer o clone
    """
    # Verifica o estado atual da instância
    response = ec2_client.describe_instances(InstanceIds=[instance_id])
    state = response['Reservations'][0]['Instances'][0]['State']['Name']
    
    if state == 'stopped':
        print(f"ℹ️  A instância {instance_id} já está parada.")
        return
    
    if state == 'stopping':
        print(f"ℹ️  A instância {instance_id} já está em processo de parada. Aguardando...")
        waiter = ec2_client.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id])
        print(f"ℹ️  A instância {instance_id} está parada.")
        return
    
    # Para a instância se estiver em qualquer outro estado
    ec2_client.stop_instances(InstanceIds=[instance_id])
    print(f"⏳ Aguardando a instância {instance_id} parar completamente...")
    
    # Usa waiter para garantir que a instância parou completamente
    waiter = ec2_client.get_waiter('instance_stopped')
    waiter.wait(InstanceIds=[instance_id])
    print(f"✅ A instância {instance_id} está parada.")

def prepare_run_params(instance, new_ami_id, ec2_client):
    """
    Prepara todos os parâmetros para criar a nova instância
    """
    # Parametros para criação da nova máquina.
    run_params = {
        'ImageId': new_ami_id,
        'InstanceType': instance['InstanceType'],
        'MaxCount': 1,
        'MinCount': 1
    }
    
    # Adiciona configurações de rede (subnet e security groups)
    run_params = add_network_config(run_params, instance, ec2_client)
    
    # Adiciona key pair se existir
    if 'KeyName' in instance:
        run_params['KeyName'] = instance['KeyName']
        print(f"🔑 Usando key pair: {instance['KeyName']}")
    
    # Adiciona user data se existir
    if 'UserData' in instance:
        run_params['UserData'] = instance['UserData']
        print("📝 User data da instância original será aplicado")
    
    # Adiciona IAM instance profile se existir
    if 'IamInstanceProfile' in instance:
        profile_name = instance['IamInstanceProfile']['Arn'].split('/')[-1]
        run_params['IamInstanceProfile'] = {'Name': profile_name}
        print(f"👤 Usando perfil IAM: {profile_name}")
    
    # Adiciona metadata options se existir
    run_params = add_metadata_options(run_params, instance)
    
    # Adiciona monitoring se habilitado
    if 'Monitoring' in instance and instance['Monitoring']['State'] == 'enabled':
        run_params['Monitoring'] = {'Enabled': True}
        print("📊 Monitoramento detalhado habilitado")
    
    # Adiciona EBS optimized se habilitado
    if 'EbsOptimized' in instance and instance['EbsOptimized']:
        run_params['EbsOptimized'] = True
        print("💾 EBS Optimized habilitado")
    
    # Adiciona placement information se existir
    run_params = add_placement_info(run_params, instance, ec2_client)
    
    # Adiciona credit specification para instâncias T
    if instance['InstanceType'].startswith('t') and 'CreditSpecification' in instance:
        if 'CpuCredits' in instance['CreditSpecification']:
            cpu_credits = instance['CreditSpecification']['CpuCredits']
            run_params['CreditSpecification'] = {
                'CpuCredits': cpu_credits
            }
            print(f"💰 Modo de créditos CPU: {cpu_credits}")
    
    # Adiciona hibernation options se habilitado
    if 'HibernationOptions' in instance and instance['HibernationOptions']['Configured']:
        run_params['HibernationOptions'] = {'Configured': True}
        print("❄️  Hibernação habilitada")
    
    # Adiciona enclave options se habilitado
    if 'EnclaveOptions' in instance and instance['EnclaveOptions']['Enabled']:
        run_params['EnclaveOptions'] = {'Enabled': True}
        print("🔒 Enclave habilitado")
    
    # Adiciona block device mappings para volumes não-raiz
    run_params = add_block_device_mappings(run_params, instance, ec2_client)
    
    return run_params

def add_network_config(run_params, instance, ec2_client):
    """
    Adiciona configurações de rede (subnet e security groups)
    """
    # Adiciona subnet se existir
    if 'SubnetId' in instance:
        run_params = add_subnet_config(run_params, instance, ec2_client)
    
    # Adiciona security groups se existir
    if 'SecurityGroups' in instance:
        security_group_ids = [sg['GroupId'] for sg in instance['SecurityGroups']]
        run_params['SecurityGroupIds'] = security_group_ids
        
        # Obtém os nomes dos security groups para exibir
        sg_names = []
        for sg_id in security_group_ids:
            try:
                sg_response = ec2_client.describe_security_groups(GroupIds=[sg_id])
                if sg_response['SecurityGroups']:
                    sg_names.append(f"{sg_id} ({sg_response['SecurityGroups'][0]['GroupName']})")
                else:
                    sg_names.append(sg_id)
            except:
                sg_names.append(sg_id)
        
        print(f"🛡️  Usando grupos de segurança: {', '.join(sg_names)}")
    
    return run_params

def add_subnet_config(run_params, instance, ec2_client):
    """
    Adiciona configuração de subnet
    """
    # Pega a AZ atual da máquina que vai ser clonada
    source_az = instance['Placement'].get('AvailabilityZone')
    
    # pega todas as AZs da região
    azs = ec2_client.describe_availability_zones()['AvailabilityZones']
    
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
        subnets = ec2_client.describe_subnets()['Subnets']
        target_subnet = None
        
        # Pega a subnet usada para a instância raiz e a VPC para o if
        source_subnet = ec2_client.describe_subnets(SubnetIds=[instance['SubnetId']])['Subnets'][0]
        source_vpc = source_subnet['VpcId']
        
        # Filtra as subnets que atendem aos critérios
        matching_subnets = [
            subnet for subnet in subnets
            if subnet['VpcId'] == source_vpc
        ]

        # Se houver subnets compatíveis, exibe e pede escolha
        if matching_subnets:
            print("\n🌐 Subnets disponíveis:")
            for id, subnet in enumerate(matching_subnets, start=1):
                name = next(
                    (tag['Value'] for tag in subnet.get('Tags', []) if tag['Key'] == 'Name'),
                    'Sem nome'
                )
                az = subnet['AvailabilityZone']
                print(f"{id} - {subnet['SubnetId']} | {name} | {az}")

            # Solicita ao user que escolha uma subnet
            while True:
                try:
                    choice = int(input("\nEscolha o número da subnet desejada: "))
                    if 1 <= choice <= len(matching_subnets):
                        target_subnet = matching_subnets[choice - 1]['SubnetId']
                        target_az = matching_subnets[choice - 1]['AvailabilityZone']
                        break
                    else:
                        print("❌ Número inválido. Tente novamente.")
                except ValueError:
                    print("❌ Entrada inválida. Digite um número.")
        else:
            # Se não houver subnets compatíveis, usa a original
            target_subnet = instance['SubnetId']
            print("⚠️  Aviso: Nenhuma subnet encontrada na VPC. Usando a subnet original.")

        # Define o parâmetro de execução
        run_params['SubnetId'] = target_subnet
        print(f"\n✅ Usando subnet: {target_subnet}")
        
        # Adiciona a AZ ao placement
        if 'Placement' not in run_params:
            run_params['Placement'] = {}
        run_params['Placement']['AvailabilityZone'] = target_az
        
        if target_az != source_az:
            print(f"🌍 Colocando nova instância em uma AZ diferente: {target_az} (original era {source_az})")
        else:
            print(f"🌍 Usando a mesma AZ da instância original: {target_az}")

    else:
        # Se houver apenas uma AZ disponivel, usa a mesma subnet
        run_params['SubnetId'] = instance['SubnetId']
        print(f"🌐 Usando a subnet original: {instance['SubnetId']}")
    
    return run_params

def add_metadata_options(run_params, instance):
    """
    Adiciona opções de metadados se existirem
    """
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
            
            # Exibe informações sobre IMDSv2
            if 'HttpTokens' in metadata_options and metadata_options['HttpTokens'] == 'required':
                print("🔐 IMDSv2 (token obrigatório) configurado")
    
    return run_params

def add_placement_info(run_params, instance, ec2_client):
    """
    Adiciona informações de placement se existirem
    """
    if 'Placement' in instance:
        placement = run_params.get('Placement', {})
        
        if 'Tenancy' in instance['Placement'] and instance['Placement']['Tenancy'] != 'default':
            placement['Tenancy'] = instance['Placement']['Tenancy']
            print(f"🏢 Tenancy: {instance['Placement']['Tenancy']}")
        
        # A AZ já é configurada na função add_subnet_config
        
        if placement:
            run_params['Placement'] = placement
    
    return run_params

def prepare_root_volume_mapping(instance, new_ami_id, ec2_client):
    """
    Prepara o mapeamento do volume raiz baseado na instância original,
    apenas se for diferente do proposto pela AMI
    
    NOTA: Esta função foi movida para ec2_volume_utils.py.
    Mantida aqui como fallback caso o módulo não esteja disponível.
    """
    try:
        # Obter o nome do dispositivo raiz da instância
        root_device_name = instance['RootDeviceName']
        
        # Encontrar o mapeamento do dispositivo raiz na instância original
        root_mapping = None
        for bdm in instance['BlockDeviceMappings']:
            if bdm['DeviceName'] == root_device_name:
                root_mapping = bdm
                break
        
        if not root_mapping or 'Ebs' not in root_mapping:
            print("ℹ️  Não foi possível obter informações do volume raiz da instância. Usando configurações da AMI.")
            return None
        
        # Obter o ID do volume raiz da instância
        root_volume_id = root_mapping['Ebs']['VolumeId']
        
        # Obter detalhes do volume raiz da instância
        instance_volume = ec2_client.describe_volumes(VolumeIds=[root_volume_id])['Volumes'][0]
        instance_volume_type = instance_volume['VolumeType']
        
        # Obter informações da AMI para comparar
        ami_info = ec2_client.describe_images(ImageIds=[new_ami_id])['Images'][0]
        ami_root_device = ami_info['RootDeviceName']
        
        # Encontrar o mapeamento do dispositivo raiz na AMI
        ami_root_mapping = None
        for bdm in ami_info.get('BlockDeviceMappings', []):
            if bdm['DeviceName'] == ami_root_device:
                ami_root_mapping = bdm
                break
        
        # Se não encontrar mapeamento na AMI, usar o da instância
        if not ami_root_mapping or 'Ebs' not in ami_root_mapping:
            print("⚠️  Não foi possível obter informações do volume raiz da AMI. Usando configurações da instância.")
        else:
            # Verificar se o tipo de volume da AMI é o mesmo da instância
            ami_volume_type = ami_root_mapping['Ebs'].get('VolumeType', 'gp2')  # padrão é gp2
            
            if instance_volume_type == ami_volume_type:
                print(f"ℹ️  Tipo de volume raiz da instância ({instance_volume_type}) é igual ao da AMI. Usando configurações padrão.")
                return None
        
        # Se chegou aqui, precisamos criar um mapeamento personalizado
        print(f"\n💾 Configurando volume raiz:")
        print(f"  - Tipo de volume da instância: {instance_volume_type}")
        if ami_root_mapping and 'Ebs' in ami_root_mapping:
            print(f"  - Tipo de volume da AMI: {ami_root_mapping['Ebs'].get('VolumeType', 'gp2')}")
        
        # Criar o mapeamento para o novo volume raiz
        new_root_mapping = {
            'DeviceName': root_device_name,
            'Ebs': {
                'DeleteOnTermination': root_mapping['Ebs'].get('DeleteOnTermination', True),
                'VolumeType': instance_volume_type,
                'Encrypted': instance_volume.get('Encrypted', False)
            }
        }
        
        # Adicionar parâmetros específicos com base no tipo de volume
        if instance_volume_type == 'gp3':
            # gp3 suporta IOPS e Throughput
            new_root_mapping['Ebs']['Iops'] = instance_volume.get('Iops', 3000)
            if 'Throughput' in instance_volume:
                new_root_mapping['Ebs']['Throughput'] = instance_volume['Throughput']
            
            # Exibe informações sobre o volume raiz
            volume_info = f"{root_device_name}: {instance_volume_type}"
            if 'Iops' in instance_volume:
                volume_info += f", {instance_volume['Iops']} IOPS"
            if 'Throughput' in instance_volume:
                volume_info += f", {instance_volume['Throughput']} MB/s throughput"
            print(f"  - Configuração aplicada: {volume_info}")
        
        elif instance_volume_type in ['io1', 'io2']:
            # io1 e io2 suportam IOPS
            if 'Iops' in instance_volume:
                new_root_mapping['Ebs']['Iops'] = instance_volume['Iops']
            
            # Exibe informações sobre o volume raiz
            volume_info = f"{root_device_name}: {instance_volume_type}"
            if 'Iops' in instance_volume:
                volume_info += f", {instance_volume['Iops']} IOPS"
            print(f"  - Configuração aplicada: {volume_info}")
        
        else:
            # Para outros tipos (gp2, st1, sc1, standard)
            print(f"  - Configuração aplicada: {root_device_name}: {instance_volume_type}")
        
        return new_root_mapping
    
    except Exception as e:
        print(f"⚠️  Erro ao configurar volume raiz: {e}. Usando configurações padrão da AMI.")
        return None

def add_block_device_mappings(run_params, instance, ec2_client):
    """
    Adiciona mapeamentos de dispositivos de bloco para volumes raiz e não-raiz
    
    NOTA: Esta função foi movida para ec2_volume_utils.py.
    Mantida aqui como fallback caso o módulo não esteja disponível.
    """
    if 'BlockDeviceMappings' not in instance:
        return run_params
    
    root_device = instance['RootDeviceName']
    block_device_mappings = []
    
    # Primeiro, adiciona o mapeamento do volume raiz
    root_mapping = prepare_root_volume_mapping(instance, None, ec2_client)
    if root_mapping:
        block_device_mappings.append(root_mapping)
    
    # Depois, adiciona os volumes não-raiz
    print("\n💾 Configurando volumes adicionais:")
    has_additional_volumes = False
    
    for bdm in instance['BlockDeviceMappings']:
        # Pula o dispositivo raiz, pois já foi tratado acima
        if bdm['DeviceName'] == root_device:
            continue
            
        if 'Ebs' in bdm:
            has_additional_volumes = True
            volume_id = bdm['Ebs']['VolumeId']
            volume = ec2_client.describe_volumes(VolumeIds=[volume_id])['Volumes'][0]
            
            # Tipo de volume
            volume_type = volume['VolumeType']
            
            new_bdm = {
                'DeviceName': bdm['DeviceName'],
                'Ebs': {
                    'VolumeSize': volume['Size'],
                    'VolumeType': volume_type,
                    'DeleteOnTermination': bdm['Ebs'].get('DeleteOnTermination', False),
                    'Encrypted': volume['Encrypted']
                }
            }
            
            # Adiciona parâmetros compatíveis com cada tipo de volume
            if volume_type == 'gp3':
                # gp3 suporta IOPS e Throughput
                new_bdm['Ebs']['Iops'] = volume.get('Iops', 3000)
                if 'Throughput' in volume:
                    new_bdm['Ebs']['Throughput'] = volume['Throughput']
            
            elif volume_type in ['io1', 'io2']:
                # io1 e io2 suportam IOPS
                if 'Iops' in volume:
                    new_bdm['Ebs']['Iops'] = volume['Iops']
            
            block_device_mappings.append(new_bdm)
            
            # Exibe informações sobre o volume
            volume_info = f"{bdm['DeviceName']}: {volume['Size']}GB {volume_type}"
            if 'Iops' in volume and volume_type in ['gp3', 'io1', 'io2']:
                volume_info += f", {volume['Iops']} IOPS"
            if 'Throughput' in volume and volume_type == 'gp3':
                volume_info += f", {volume['Throughput']} MB/s throughput"
            print(f"  - {volume_info}")
    
    if not has_additional_volumes:
        print("  - Nenhum volume adicional encontrado além do volume raiz")
    
    if block_device_mappings:
        run_params['BlockDeviceMappings'] = block_device_mappings
    
    return run_params

def apply_tags(ec2_client, source_instance_id, target_instance_id, new_name=None):
    """
    Aplica tags na nova instância
    """
    print("Copiando tags da instância original...")
    tags_response = ec2_client.describe_tags(
        Filters=[{'Name': 'resource-id', 'Values': [source_instance_id]}]
    )
    
    # Pega o mes e ano atual
    current_date = datetime.now().strftime("%d/%m/%Y")
    
    if tags_response['Tags']:
        tags_to_apply = []
        original_name = None
        
        # Primeiro, encontra a tag Name original se existir
        for tag in tags_response['Tags']:
            if tag['Key'].startswith('aws:'):
                continue

            if tag['Key'] == 'Name':
                original_name = tag['Value']
                break
        
        for tag in tags_response['Tags']:
            if tag['Key'].startswith('aws:'):
                continue
                
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
        
        source_region = ec2_client.meta.region_name
        tags_to_apply.append({
            'Key': 'SourceRegion',
            'Value': source_region
        })
        
        ec2_client.create_tags(
            Resources=[target_instance_id],
            Tags=tags_to_apply
        )
