import requests
from datetime import datetime, timedelta

# Configuration
PROMETHEUS_URL = ""  # Replace with your Prometheus URL

# Time range (last 1 hour, 30-second intervals)
END_TIME = datetime.now()
START_TIME = END_TIME - timedelta(minutes=20)
STEP = "30s"
OUTPUT_FILE = "worker_cpu_usage.txt"  # Output text file name
def get_worker_nodes():
    """Fetch all worker nodes using kube_node_role metric."""
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={
                "query": 'kube_node_role{role="worker"}',
                "time": END_TIME.timestamp()
            }
        )
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return [result["metric"]["node"] for result in data["data"]["result"]]
        else:
            print(f"Error fetching worker nodes: {data.get('error', 'Unknown error')}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch worker nodes: {e}")
        return []

def query_worker_cpu_usage(nodes):
    """Calculate CPU usage percentage for worker nodes."""
    if not nodes:
        print("No worker nodes found.")
        return

    # Create regex pattern for worker nodes (e.g., "^node1$|^node2$")
    node_regex = "|".join([f"^{node}$" for node in nodes])
    
    # Build the PromQL query
    promql_query = f'''
        (
          sum(
            rate(container_cpu_usage_seconds_total{{node=~"{node_regex}"}}[1m])
            * on(node) group_left(role)
            kube_node_role{{role="worker"}}
          )
        )
        /
        (
          sum(
            machine_cpu_cores{{node=~"{node_regex}"}}
            * on(node) group_left(role)
            kube_node_role{{role="worker"}}
          )
        )
        * 100
    '''

    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": promql_query,
                "start": START_TIME.timestamp(),
                "end": END_TIME.timestamp(),
                "step": STEP,
            }
        )
        response.raise_for_status()
        data = response.json()
        print(data["data"]["result"])
        if data["status"] == "success":
            results = data["data"]["result"]
            if not results:
                print("No CPU usage data found for worker nodes.")
                return

            print("\nWorker Nodes CPU Usage (%):")
            for timestamp, value in results[0]["values"]:
                human_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {human_time}: {float(value):.2f}%")
            with open(OUTPUT_FILE, "w") as f:
                f.write("Worker Nodes CPU Usage (%):\n")
                for timestamp, value in results[0]["values"]:
                    human_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{human_time}: {float(value):.2f}%\n")
            print(f"Data written to {OUTPUT_FILE}")

        else:
            print(f"Error: {data.get('error', 'Unknown error')}")

    except requests.exceptions.RequestException as e:
        print(f"Failed to query Prometheus: {e}")



if __name__ == "__main__":
    worker_nodes = get_worker_nodes()
    query_worker_cpu_usage(worker_nodes)