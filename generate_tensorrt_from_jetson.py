import subprocess

SAVE_DIRECTORY = r'/home/jetson/edge_server/images'
container_name = 'ultralytics/ultralytics:latest-jetson-jetpack4'

# Command to get docker container ID
command_get_container_id = [
    'sudo', 'docker', 'ps', '-aq', '-f', f'name={container_name}'
]

# Run the command to get the container ID
result = subprocess.run(command_get_container_id, capture_output=True, text=True)
container_id = result.stdout.strip()

# Command to run docker and mount the volume
command_docker_run = [
    'sudo', 'docker', 'run', '-v', f'{SAVE_DIRECTORY}:/ultralytics/images:rw', container_id
]

# Run the docker mount command
subprocess.run(command_docker_run)

# Command to export the model using YOLO
command_export_tensorrt = [
    'yolo', 'export', 'model=best_v8n.pt', 'format=engine'
]

# Run the export command
subprocess.run(command_export_tensorrt)