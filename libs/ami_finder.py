#!/usr/bin/env python3

def find_instance_amis(ec2_client, instance_id):
    """
    Busca as AMIs mais recentes criadas a partir da instância especificada
    """
    print(f"🔍 Buscando AMIs disponíveis para a instância {instance_id}...")
    
    try:
        # Busca todas as AMIs de propriedade da conta atual
        response = ec2_client.describe_images(
            Owners=['self'],
            Filters=[
                {
                    'Name': 'state',
                    'Values': ['available']
                }
            ]
        )
        
        # Filtra as AMIs que contêm o ID da instância na descrição (criadas pelo AWS Backup)
        instance_amis = []
        for image in response['Images']:
            description = image.get('Description', '')
            name = image.get('Name', '')
            
            # Verifica se o ID da instância está na descrição ou no nome
            if instance_id in description or instance_id in name:
                # Adiciona informações relevantes
                creation_date = image.get('CreationDate', '')
                instance_amis.append({
                    'ImageId': image['ImageId'],
                    'CreationDate': creation_date,
                    'Description': description,
                    'Name': name
                })
        
        # Ordena as AMIs por data de criação (mais recente primeiro)
        instance_amis.sort(key=lambda x: x['CreationDate'], reverse=True)
        
        if not instance_amis:
            print(f"⚠️  Nenhuma AMI encontrada para a instância {instance_id}.")
            return None
        
        # Pega as 3 AMIs mais recentes (ou menos se não houver 3)
        recent_amis = instance_amis[:min(3, len(instance_amis))]
        
        print(f"\n📋 AMIs mais recentes para a instância {instance_id}:")
        
        for i, ami in enumerate(recent_amis, 1):
            # Formata a data de criação para exibição
            creation_date = ami['CreationDate'].split('T')[0]  # Pega apenas a parte da data
            
            # Exibe informações da AMI
            print(f"{i} - {ami['ImageId']} | {creation_date} | {ami['Name'] or ami['Description'][:50]}")
        
        # Pede ao usuário para escolher uma AMI
        while True:
            choice = input("\nEscolha o número da AMI desejada (ou pressione Enter para usar a mais recente): ")
            
            if choice == "":
                # Usa a AMI mais recente
                selected_ami = recent_amis[0]['ImageId']
                print(f"✅ Usando a AMI mais recente: {selected_ami}")
                return selected_ami
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(recent_amis):
                    selected_ami = recent_amis[choice_num - 1]['ImageId']
                    print(f"✅ AMI selecionada: {selected_ami}")
                    return selected_ami
                else:
                    print(f"❌ Número inválido. Escolha entre 1 e {len(recent_amis)}.")
            except ValueError:
                print("❌ Entrada inválida. Digite um número ou pressione Enter.")
    
    except Exception as e:
        print(f"❌ Erro ao buscar AMIs: {e}")
        return None
