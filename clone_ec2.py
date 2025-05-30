#!/usr/bin/env python3

import argparse
import sys
try:
    from libs.ec2_clone_functions import clone_instance_with_new_ami
    from libs.ami_finder import find_instance_amis
except ImportError as e:
    if "boto3" in str(e):
        print("ERRO: Lib boto3 é necessária para a execução. Instale com: pip install boto3")
    else:
        print(f"ERRO: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Clona uma instância EC2 com uma nova AMI preservando todas as configurações',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Clona a instância desejada com uma nova AMI
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --profile dev
  
  # Clona a instância desejada com uma nova AMI com um novo nome
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer --profile dev
  
  # Clona a instância desejada buscando automaticamente as AMIs mais recentes
  %(prog)s --instance-id i-0123456789abcdef0 --profile dev --region us-east-1
        """
    )
    
    parser.add_argument('--instance-id', required=True, 
                        help='ID da instância a ser clonada (ex: i-0123456789abcdef0)')
    parser.add_argument('--new-ami-id', 
                    help='ID da nova AMI a ser usada (ex: ami-0abcdef1234567890). Se não for fornecido, o script buscará automaticamente as AMIs mais recentes da instância.')
    parser.add_argument('--profile', required=True, default='dev',
                        help='Nome do perfil AWS (ex: dev, hml, prd etc... | Padrão: dev)')
    parser.add_argument('--new-name', 
                        help='Novo nome para a instância. Será formatado como <novo-nome>-DR-DD/MM/AAAA')
    parser.add_argument('--region', default='us-east-1', 
                        help='Região AWS onde a instância de origem está localizada (padrão: us-east-1)')
    
    args = parser.parse_args()
    
    try:
        # Configurar sessão AWS
        import boto3
        session = boto3.Session(profile_name=args.profile, region_name=args.region)
        ec2_client = session.client('ec2')
        
        # Se não foi fornecido um ID de AMI, buscar automaticamente
        ami_id = args.new_ami_id
        if not ami_id:
            ami_id = find_instance_amis(ec2_client, args.instance_id)
            if not ami_id:
                print("ERRO: Não foi possível encontrar uma AMI para a instância. Por favor, especifique uma AMI usando --new-ami-id.")
                sys.exit(1)
        
        # Clonar a instância
        clone_instance_with_new_ami(
            args.instance_id, 
            ami_id, 
            args.profile,
            args.new_name, 
            args.region
        )
    except Exception as e:
        print(f"ERRO: Falha ao clonar instância: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
