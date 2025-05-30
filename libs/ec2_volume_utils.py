#!/usr/bin/env python3
import sys

def prepare_root_volume_mapping(instance, new_ami_id, ec2_client):
    """
    Prepara o mapeamento do volume raiz baseado na instância original,
    apenas se for diferente do proposto pela AMI
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
