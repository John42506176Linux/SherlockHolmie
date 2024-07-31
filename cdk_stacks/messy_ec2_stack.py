import aws_cdk as core
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_elasticloadbalancingv2 as elbv2
from constructs import Construct

class ReportEC2Stack(core.Stack):
    def __init__(self, scope: Construct, id: str, vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)


        # Define the Security Group
        security_group = ec2.SecurityGroup(self, "ProdSecurityGroup",
                                           vpc=vpc.vpc,
                                           description="Allow HTTP access to EC2 instance",
                                           allow_all_outbound=True)
        security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "Allow HTTP traffic")

        # Define the EC2 instance
        instance_type = ec2.InstanceType("t3.2xlarge")  # Provides 16,384 MiB of memory
        instance = ec2.Instance(self, "ProdInstanceLoadBalancer",
                                instance_type=instance_type,
                                machine_image=ec2.AmazonLinuxImage(),
                                vpc=vpc.vpc,
                                security_group=security_group,
                                key_name="sherlock-aws-key" )

        

        # Output the EC2 instance public IP address
        core.CfnOutput(self, "InstancePublicIP",
                       value=instance.instance_public_ip,
                       description="The public IP address of the EC2 instance")