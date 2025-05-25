#!/usr/bin/env python3

import argparse
import sys
try:
    from libs.ec2_clone_functions import clone_instance_with_new_ami
except ImportError as e:
    if "boto3" in str(e):
        print("ERRO: Lib boto3 é necessária para a execução. Instale com: pip install boto3")
    else:
        print(f"ERRO: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Clone an EC2 instance with a new AMI while preserving all settings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clona a instância desejada com uma nova AMI para a mesma região
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --profile dev
  
  # Clona a instância desejada com uma nova AMI para a mesma região com um novo nome
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer --profile dev
  
  # Clona a instância desejada com uma nova AMI para uma região diferente
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --target-region us-west-2 --profile dev
        """
    )
    
    parser.add_argument('--instance-id', required=True, 
                        help='ID of the instance to clone (e.g., i-0123456789abcdef0)')
    parser.add_argument('--new-ami-id', required=True, 
                        help='ID of the new AMI to use (e.g., ami-0abcdef1234567890)')
    parser.add_argument('--profile', required=True, default='dev',
                        help='Profile name (e.g., dev, hml, prd e etc... | Default: dev)')
    parser.add_argument('--new-name', 
                        help='New name for the instance. Will be formatted as <new-name>-DR-MM/YYYY')
    parser.add_argument('--region', default='us-east-1', 
                        help='AWS region where the source instance is located (default: us-east-1)')
    parser.add_argument('--target-region', 
                        help='AWS region where to create the new instance. If not specified, uses the same region as source.')
    
    args = parser.parse_args()
    
    try:
        clone_instance_with_new_ami(
            args.instance_id, 
            args.new_ami_id, 
            args.profile,
            args.new_name, 
            args.region,
            args.target_region
        )
    except Exception as e:
        print(f"ERROR: Failed to clone instance: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
