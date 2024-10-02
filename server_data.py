import socket
import os
import subprocess

# Directory to save the received files
save_directory = r'/home/jetson/edge_server/images'  # Update with your actual path

# Function to run YOLOv8 inference using Docker
def run_inference(image_path):
    print(f'Running YOLOv8 inference on {image_path}...')
    # This assumes your YOLOv8 Docker container is set up correctly
    command = [
        'sudo', 'docker', 'run', '-it', '--rm', '--ipc=host', '--runtime=nvidia',
        '-v', f'{save_directory}:/ultralytics/images:rw',
        'ultralytics/ultralytics:latest-jetson-jetpack4',
        'yolo', 'detect', 'predict',
        f'source=images/{os.path.basename(image_path)}',
        'model=images/best_v8n.pt',
        'project=images/pred',
        'save_txt',
        'exist_ok=True'
    ]
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print(result.stdout)
        print('Inference completed successfully.')
        
    except subprocess.CalledProcessError as e:
        print(f'Error running YOLOv8 inference: {e}')
        print(f'Error output: {e.stderr}')

# Creating server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 12345))
server_socket.listen(1)

print('Waiting for connection from client...')

while True:
    try:
        conn, addr = server_socket.accept()
        print(f'Connected with {addr}')

        # Receive the file name
        file_name = conn.recv(1024).decode('utf-8', errors='ignore').strip()

        if not file_name:
            print("Empty or invalid file name.")
            continue

        file_path = os.path.join(save_directory, file_name)
        print(f'Receiving file {file_name}...')

        # Receive and save the file
        with open(file_path, 'wb') as f:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                f.write(data)

        print(f'File successfully saved at {file_path}')

        # Trigger YOLOv8 inference on the received image
        run_inference(file_path)

    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        # Close connection
        if 'conn' in locals():
            conn.close()