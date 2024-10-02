import socket
import os
import subprocess
import time
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

# Directory to save the received files
SAVE_DIRECTORY = r'/home/jetson/edge_server/images'  # Update with your actual path
MAX_WORKERS = 4  # Adjust based on your system's capabilities
DOCKER_CONTAINER_NAME = 'ultralytics_inference'

# Function to remove existing Docker container
def remove_existing_container():
    print('Checking for existing container...')
    command = ['sudo', 'docker', 'ps', '-aq', '-f', f'name={DOCKER_CONTAINER_NAME}']
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        container_id = result.stdout.strip()
        if container_id:
            print(f'Removing existing container {container_id}...')
            remove_command = ['sudo', 'docker', 'rm', '-f', container_id]
            subprocess.run(remove_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            print('Existing container removed successfully.')
        else:
            print('No existing container found.')
    except subprocess.CalledProcessError as e:
        print(f'Error checking/removing existing container: {e}')
        print(f'Error output: {e.stderr}')

# Function to start the Docker container once
def start_docker_container():
    remove_existing_container()
    print('Starting YOLOv8 Docker container...')
    command = [
        'sudo', 'docker', 'run', '-d', '--name', DOCKER_CONTAINER_NAME, '--ipc=host', '--runtime=nvidia',
        '-v', f'{SAVE_DIRECTORY}:/ultralytics/images:rw',
        'ultralytics/ultralytics:latest-jetson-jetpack4', 'sleep', 'infinity'
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('Docker container started successfully.')
    except subprocess.CalledProcessError as e:
        print(f'Error starting Docker container: {e}')
        print(f'Error output: {e.stderr}')
        exit(1)

# Function to stop the Docker container
def stop_docker_container():
    print('Stopping YOLOv8 Docker container...')
    command = ['sudo', 'docker', 'stop', DOCKER_CONTAINER_NAME]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('Docker container stopped successfully.')
    except subprocess.CalledProcessError as e:
        print(f'Error stopping Docker container: {e}')
        print(f'Error output: {e.stderr}')

# Function to run YOLOv8 inference using the running Docker container
def run_inference(image_path):
    print(f'Running YOLOv8 inference on {image_path}...')
    command = [
        'sudo', 'docker', 'exec', DOCKER_CONTAINER_NAME,
        'yolo', 'detect', 'predict',
        f'source=images/{os.path.basename(image_path)}',
        'model=images/best_v8n.pt',
        'project=images/pred',
        'save_txt',
        'exist_ok=True'
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('Inference completed successfully.')
        return f'images/pred/predict/{os.path.basename(image_path)}'
    except subprocess.CalledProcessError as e:
        print(f'Error running YOLOv8 inference: {e}')
        print(f'Error output: {e.stderr}')
        return None

def send_file(conn, file_path):
    with open(file_path, 'rb') as f:
        file_data = f.read()
    
    file_name = os.path.basename(file_path).encode('utf-8')
    name_length = len(file_name)
    file_size = len(file_data)

    # Send file name length, file name, and file size
    conn.sendall(struct.pack('!I', name_length))
    conn.sendall(file_name)
    conn.sendall(struct.pack('!Q', file_size))

    # Send file data
    conn.sendall(file_data)
    print(f'Sent file: {file_path}')

def receive_file(conn, save_directory):
    # Receive file name length
    name_length = struct.unpack('!I', conn.recv(4))[0]

    # Receive file name
    file_name = conn.recv(name_length).decode('utf-8')
    file_path = os.path.join(save_directory, file_name)

    # Receive file size
    file_size = struct.unpack('!Q', conn.recv(8))[0]

    print(f'Receiving file: {file_name}, Size: {file_size} bytes')

    # Receive and save the file
    with open(file_path, 'wb') as f:
        remaining = file_size
        while remaining > 0:
            chunk_size = 4096 if remaining > 4096 else remaining
            chunk = conn.recv(chunk_size)
            if not chunk:
                raise ConnectionError("Connection closed while receiving file")
            f.write(chunk)
            remaining -= len(chunk)

    print(f'File successfully saved at {file_path}')
    return file_path

def handle_client(conn, addr, inference_queue):
    print(f'Connected with {addr}')
    try:
        file_path = receive_file(conn, SAVE_DIRECTORY)
        if file_path:
            # Add the inference task to the queue
            inference_queue.put((conn, file_path))
        else:
            print("File reception failed.")
    except Exception as e:
        print(f'An error occurred while handling client: {e}')
    finally:
        # Don't close the connection here, it will be closed after sending the result
        pass

def inference_worker(inference_queue):
    while True:
        conn, file_path = inference_queue.get()
        try:
            predicted_image_path = run_inference(file_path)
            if predicted_image_path and os.path.exists(predicted_image_path):
                send_file(conn, predicted_image_path)
            else:
                print("Predicted image not found or inference failed.")
                conn.send(b"INFERENCE_FAILED")
        except Exception as e:
            print(f'An error occurred during inference: {e}')
        finally:
            conn.close()
            print("Connection closed.")
            inference_queue.task_done()

def main():
    start_docker_container()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 12345))
    server_socket.listen(5)
    print('Server is listening for connections...')

    inference_queue = queue.Queue()

    # Start inference workers
    for _ in range(MAX_WORKERS):
        threading.Thread(target=inference_worker, args=(inference_queue,), daemon=True).start()

    try:
        with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust max_workers as needed
            while True:
                conn, addr = server_socket.accept()
                executor.submit(handle_client, conn, addr, inference_queue)
    except KeyboardInterrupt:
        print('Shutting down server...')
    finally:
        stop_docker_container()

if __name__ == "__main__":
    main()
