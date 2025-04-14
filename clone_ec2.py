#!/usr/bin/env python3
"""
EC2 Instance Cloner

This script clones an existing EC2 instance with a new AMI while preserving all other settings
including security groups, IAM roles, tags, metadata options, and EBS volumes.
It can clone within the same region or across different AWS regions.

Prerequisites:
    - Python 3.6+
    - boto3 library (install with: pip install boto3)
    - AWS credentials configured (~/.aws/credentials or environment variables)
    - Appropriate IAM permissions to describe and create EC2 instances

Examples:
    # Basic usage
    python clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890
    
    # With custom name and region
    python clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer --region eu-west-1
    
    # Cross-region cloning
    python clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --target-region us-west-2
"""
import argparse
import sys
try:
    from libs.ec2_clone_functions import clone_instance_with_new_ami
except ImportError as e:
    if "boto3" in str(e):
        print("ERROR: boto3 library is required. Install it with: pip install boto3")
    else:
        print(f"ERROR: {e}")
    sys.exit(1)

def main():
    """
    Main function to parse arguments and call the clone function
    """
    parser = argparse.ArgumentParser(
        description='Clone an EC2 instance with a new AMI while preserving all settings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clone instance with a new AMI in the same region
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1
  
  # Clone instance with a new AMI and custom name
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer
  
  # Clone instance to a different region
  %(prog)s --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --target-region us-west-2
        """
    )
    
    parser.add_argument('--instance-id', required=True, 
                        help='ID of the instance to clone (e.g., i-0123456789abcdef0)')
    parser.add_argument('--new-ami-id', required=True, 
                        help='ID of the new AMI to use (e.g., ami-0abcdef1234567890)')
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
            args.new_name, 
            args.region,
            args.target_region
        )
    except Exception as e:
        print(f"ERROR: Failed to clone instance: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
