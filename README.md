#Deepseek-K8S-Autoscaler-MCP

## Intro
This repo allows one to scale up or scale down a K8S cluster managed by [KubeSpray](https://github.com/kubernetes-sigs/kubespray) and Terraform. 

## Prerequisites
To use this tool, there are a number of parameters that needs to be filled out in **autoscaler-client.py**, **autoscaler-server.py**, **getPrice.py**, **worker-promq.py** including Deepseek API KEY, credentials from cloud providers.etc.

## Infrastructure
The infrastructure which hosts the K8S cluster used by this repo can be referenced [here](https://github.com/aqzzaq/infra-demo). The cluster contains resources from AWS, Azure, and GCP.

## Usage
Execute the client using command `python autoscaler-client.py`. The specific behavior of the Deepseek LLM is configurable by modifying the query in the **autoscaler-client.py**. 
Default behavior of the current query will first check the prometheus endpoint in **worker-promq.py** for the worker nodes cpu usage and decides whether to scale up or down the K8S cluster.
If the Deepseek LLM decides to scale up the cluster, current query will first check for the lowest-priced on-Demand instance using **getPrice.py** and then scale the cluster with the node from the cheapest provider.

