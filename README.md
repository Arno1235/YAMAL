# YAMAL (Yet Another Messaging and Asynchronous Launch)

YAMAL is a lightweight Python framework designed for easily running nodes in parallel and facilitating communication between them using YAML launch files. Inspired by the functionality of ROS (Robot Operating System), YAMAL aims to provide a streamlined and minimalistic alternative for applications that require parallel processing and inter-node communication.

## Key Features:
- **Lightweight**: YAMAL is designed to be minimalistic and lightweight, making it suitable for resource-constrained environments.
- **Parallel Node Execution**: Easily run multiple nodes in parallel to perform concurrent tasks.
- **YAML Launch Files**: YAMAL utilizes YAML files for launching and configuring nodes, providing a simple and human-readable format for defining node configurations and interconnections.
- **Inter-Node Communication**: Nodes can communicate with each other seamlessly using YAMAL's messaging system, allowing for efficient data exchange and coordination.

## Getting Started:
To start using YAMAL, simply install the package and create YAML launch files to define your node configurations. YAMAL provides intuitive APIs for creating and managing nodes, as well as sending and receiving messages between them.

## Example Usage:
```python
import yamal

# Define node configurations in a YAML launch file
launch_file = "example_launch.yaml"

# Launch nodes based on the YAML configuration
yamal.launch(launch_file)

# Perform additional operations with the running nodes
...

# Shutdown nodes when finished
yamal.shutdown()
