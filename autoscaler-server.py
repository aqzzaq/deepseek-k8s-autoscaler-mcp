# basic import 
from mcp.server.fastmcp import FastMCP
import os
from python_terraform import *
from langchain_community.document_loaders import TextLoader
import worker_promq
import yaml
import ansible_runner
import getPrice
from kubernetes import client, config

HOST_FILE = ""
TERRAFORM_DIR = ""
TERRAFORM_STATE_BACKEND_DIR = ""
TERRAFORM_VAR_SHARED_SECRET = ""
TERRAFORM_VAR_GCP_VPC_NAME = "" 
TERRAFORM_VAR_GCP_SUBNET_NAME = ""
TERRAFORM_VAR_AWS_PRIVATE_SUBNET_ID = ""
TERRAFROM_VAR_AWS_SECURITY_GROUP_ID = ""
TERRAFORM_VAR_AZURE_SUBNET_ID = ""
ANSIBLE_PLAYBOOK_DIR = ""
ANSIBLE_USER = ""
ANSIBLE_SSH_KEY_PATH = ""
K8S_KUBECONFIG_PATH = ""

# instantiate an MCP server client
mcp = FastMCP("K8S Autoscaler")


def get_node_name(hosts_file):
    with open(hosts_file) as f:
        hosts = yaml.safe_load(f)
    nodes = hosts["all"]["hosts"].keys()
    temp_scaling_nodes = [item for item in nodes if "temp-scaling-node" in item]
    current_node = current_node = max((int(item.split("-")[-1]) for item in temp_scaling_nodes), default=0)
    return current_node

def get_cloud_provider(hosts_file, node_name_suffix):
    with open(hosts_file) as f:
        hosts = yaml.safe_load(f)
    nodes = hosts["all"]["hosts"].keys()
    cloud_provider = next((item for item in nodes if node_name_suffix in item), None).split("-")[0]
    return cloud_provider

def k8s_label_node(node_name, label_key, label_value):
    # Load kubeconfig (usually from ~/.kube/config)
    config.load_kube_config(config_file=K8S_KUBECONFIG_PATH)
    
    # Create a CoreV1Api client
    api = client.CoreV1Api()
    
    try:
        # Get the node object
        node = api.read_node(node_name)
        
        # Add/update the label
        node.metadata.labels[label_key] = label_value
        
        # Patch the node
        api.patch_node(node_name, node)
    except client.ApiException as e:
        return(f"Error: {e}")

# DEFINE TOOLS

@mcp.tool()
def terraform_create_google_instance():
    """
    Create K8S worker node from GCP.
    """
    current_node = str(get_node_name(HOST_FILE) + 1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, target='module.gcp_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'scale_operation': 'true','shared_secret': TERRAFORM_VAR_SHARED_SECRET, 'gcp_worker_count':'1', 'gcp_vpc_name': TERRAFORM_VAR_GCP_VPC_NAME, 'gcp_subnet_name': TERRAFORM_VAR_GCP_SUBNET_NAME, 'gcp_compute_instance_worker_name': f'scaling-run{current_node}-worker-node'})
    return stdout

@mcp.tool()
def terraform_create_aws_instance():
    """
    Create K8S worker node from AWS.
    """
    current_node = str(get_node_name(HOST_FILE) + 1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, target='module.aws_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'scale_operation': 'true', 'shared_secret': TERRAFORM_VAR_SHARED_SECRET, 'aws_worker_count':'1', 'aws_private_subnet_id': TERRAFORM_VAR_AWS_PRIVATE_SUBNET_ID, 'aws_security_group_id':TERRAFROM_VAR_AWS_SECURITY_GROUP_ID, 'aws_ec2_worker_name': f'scaling-run{current_node}-worker-node'})
    return stdout

@mcp.tool()
def terraform_create_azure_instance():
    """
    Create K8S worker node from Azure.
    """
    current_node = str(get_node_name(HOST_FILE) + 1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, target='module.azure_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'scale_operation': 'true', 'shared_secret': TERRAFORM_VAR_SHARED_SECRET, 'azure_worker_count':'1', 'azure_subnet_id': TERRAFORM_VAR_AZURE_SUBNET_ID}, 'azure_vm_worker_name': f'scaling-run{current_node}-worker-node' )
    print(stdout)
    return stdout

@mcp.tool()
def kubespray_add_worker_instance_to_cluster(instance_ip, cloud_provider):
    """
    Add a worker instance to kubernetes cluster. Should be executed only after worker node is created from cloud providers. 
    """
    with open(HOST_FILE) as f:
        hosts = yaml.safe_load(f)
    current_node = str(get_node_name(HOST_FILE) + 1) 
    node_name = cloud_provider.lower() + "-temp-scaling-node-" + current_node

    host_info = {
        "ansible_host": instance_ip,
        "ip": instance_ip,
        "access_ip": instance_ip
    }

    hosts["all"]["hosts"][node_name] = host_info
    hosts["all"]["children"]["kube_node"]["hosts"][node_name] = None
    
    with open(HOST_FILE, "w") as file:
        yaml.dump(hosts, file)

    response = ansible_runner.run(
        playbook="scale.yml",
        inventory=HOST_FILE,
        envvars={
            "ANSIBLE_PRIVATE_KEY_FILE": ANSIBLE_SSH_KEY_PATH
        },
        cmdline="-u " + ANSIBLE_USER +" -b -v",
        project_dir=ANSIBLE_PLAYBOOK_DIR  # Critical for path resolution
    )
    if response.status == "successful":
        k8s_label_node(node_name, "node-role.kubernetes.io/worker", "worker")
        return "Playbook succeeded!, Final status:", response.status
    else:
        return "Error:", response.rc   # Return code

@mcp.tool()
def terraform_destroy_google_instance():
    """
    Destroy K8S worker node from GCP. Should be executed only after GCP worker node is removed from kubernetes cluster.
    """
    current_node = str(get_node_name(HOST_FILE)+1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, auto_approve=True, destroy=True, target='module.gcp_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'shared_secret': TERRAFORM_VAR_SHARED_SECRET})
    return stdout

@mcp.tool()
def terraform_destroy_aws_instance():
    """
    Destroy K8S worker node from AWS. Should be executed only after AWS worker node is removed from kubernetes cluster.
    """
    current_node = str(get_node_name(HOST_FILE)+1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, auto_approve=True, destroy=True, target='module.aws_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'shared_secret': TERRAFORM_VAR_SHARED_SECRET})
    return stdout

@mcp.tool()
def terraform_destroy_azure_instance():
    """
    Destroy K8S worker node from Azure. Should be executed only after Azure worker node is removed from kubernetes cluster.
    """
    current_node = str(get_node_name(HOST_FILE)+1) 
    tf = Terraform(working_dir=TERRAFORM_DIR)
    tf.init()
    return_code, stdout, stderr = tf.apply(skip_plan=True, auto_approve=True, destroy=True, target='module.azure_worker_node', state=f'{TERRAFORM_STATE_BACKEND_DIR}/scaling-{current_node}.state', var={'shared_secret': TERRAFORM_VAR_SHARED_SECRET})
    return stdout

@mcp.tool()
def kubespray_remove_worker_instance_from_cluster():
    """
    Remove a worker instance from the kubernetes cluster. This tool will identify which node to be removed and also return the cloud provider during the removal process."
    """
    current_node = str(get_node_name(HOST_FILE))
    if int(current_node) == 0:
        return "There are no more nodes to be removed."
    
    node_name_suffix = "temp-scaling-node-" + current_node
    cloud_provider = get_cloud_provider(HOST_FILE, node_name_suffix)
    node_name = cloud_provider + "-temp-scaling-node-" + current_node

    response = ansible_runner.run(
        playbook="remove-node.yml",
        inventory=HOST_FILE,
        envvars={
            "ANSIBLE_PRIVATE_KEY_FILE": ANSIBLE_SSH_KEY_PATH
        },
        extravars={"node": node_name, "skip_confirmation": "true"},
        cmdline="-u " + ANSIBLE_USER +" -b -v",   
        project_dir=ANSIBLE_PLAYBOOK_DIR  # Critical for path resolution
    )
    if response.status == "successful":
        with open(HOST_FILE) as f:
            hosts = yaml.safe_load(f)
        hosts["all"]["hosts"].pop(node_name)
        hosts["all"]["children"]["kube_node"]["hosts"].pop(node_name)
        with open(HOST_FILE, "w") as file:
            yaml.dump(hosts, file)
        return f"{cloud_provider} node has been removed from K8S cluster. Final status:", response.status
    else:
        return "Error:", response.rc   # Return code


@mcp.tool()
def get_cloud_price():
    """
    Get the lowest on-demand instance price from GCP, Azure and AWS.
    """
    return getPrice.compare_prices()


@mcp.tool()
def get_worker_cpu_usage():
    """
    Get CPU Usage Info on K8S Cluster Worker Nodes
    """
    worker_nodes = worker_promq.get_worker_nodes()
    worker_promq.query_worker_cpu_usage(worker_nodes)
    loader = TextLoader("./worker_cpu_usage.txt")
    monitor_data = loader.load()
    return monitor_data[0].page_content

 # execute and return the stdio output
if __name__ == "__main__":
    mcp.run(transport="stdio")
