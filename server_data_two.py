import socket
import os
import subprocess
import time
import struct

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
        return f'images/pred/predict/{os.path.basename(image_path)}'
    except subprocess.CalledProcessError as e:
        print(f'Error running YOLOv8 inference: {e}')
        print(f'Error output: {e.stderr}')
        return None

def send_file(conn, file_path):
    file_name = os.path.basename(file_path)
    conn.send(file_name.encode())
    time.sleep(0.1)  # Give client time to prepare for file reception
    
    file_size = os.path.getsize(file_path)
    conn.send(struct.pack('!Q', file_size))
    
    with open(file_path, 'rb') as f:
        bytes_sent = 0
        while bytes_sent < file_size:
            chunk = f.read(4096)
            if not chunk:
                break
            conn.sendall(chunk)
            bytes_sent += len(chunk)
    print(f'Sent file: {file_name}')

def receive_file(conn, save_directory):
    # Receive the file name
    file_name = conn.recv(1024).decode('utf-8', errors='ignore').strip()

    if not file_name:
        print("Empty or invalid file name.")
        return None

    file_path = os.path.join(save_directory, file_name)
    print(f'Receiving file {file_name}...')

    # Receive the file size
    file_size = struct.unpack('!Q', conn.recv(8))[0]

    # Receive and save the file
    with open(file_path, 'wb') as f:
        bytes_received = 0
        while bytes_received < file_size:
            chunk = conn.recv(min(4096, file_size - bytes_received))
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    print(f'File successfully saved at {file_path}')
    return file_path

# Creating server socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 12345))
server_socket.listen(1)

print('Waiting for connection from client...')

while True:
    try:
        conn, addr = server_socket.accept()
        print(f'Connected with {addr}')

        file_path = receive_file(conn, save_directory)

        if file_path:
            # Trigger YOLOv8 inference on the received image
            predicted_image_path = run_inference(file_path)
            print(predicted_image_path)

            if predicted_image_path and os.path.exists(predicted_image_path):
                # Send the predicted image back to the client
                send_file(conn, predicted_image_path)
            else:
                print("Predicted image not found or inference failed.")
                conn.send(b"INFERENCE_FAILED")
        else:
            print("File reception failed.")

    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        # Close connection
        if 'conn' in locals():
            conn.close()
        print("Connection closed.")