import socket
import os
import subprocess
import time
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import queue
import json
import cv2

SAVE_DIRECTORY = r'/home/jetson/edge_server/images' 
MAX_WORKERS = 4  
DOCKER_CONTAINER_NAME = 'ultralytics_inference'

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

def stop_docker_container():
    print('Stopping YOLOv8 Docker container...')
    command = ['sudo', 'docker', 'stop', DOCKER_CONTAINER_NAME]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        print('Docker container stopped successfully.')
    except subprocess.CalledProcessError as e:
        print(f'Error stopping Docker container: {e}')
        print(f'Error output: {e.stderr}')

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
        file_name = os.path.basename(image_path)
        pure_name = os.path.splitext(file_name)[0]
        return pure_name
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

    conn.sendall(struct.pack('!I', name_length))
    conn.sendall(file_name)
    conn.sendall(struct.pack('!Q', file_size))

    conn.sendall(file_data)
    print(f'Sent file: {file_path}')

def receive_file(conn, save_directory):
    name_length = struct.unpack('!I', conn.recv(4))[0]

    file_name = conn.recv(name_length).decode('utf-8')
    file_path = os.path.join(save_directory, file_name)

    file_size = struct.unpack('!Q', conn.recv(8))[0]

    print(f'Receiving file: {file_name}, Size: {file_size} bytes')

    with open(file_path, 'wb') as f:
        remaining = file_size
        while remaining > 0:
            chunk_size = 4096 if remaining > 4096 else remaining
            chunk = conn.recv(chunk_size)
            if not chunk:
                raise ConnectionError("Connection closed while receiving file")
            f.write(chunk)
            remaining -= len(chunk)

    img = cv2.imread(file_path)
    h, w, _ = img.shape
    crop_size = min(h, w)
    center_x = w // 2
    center_y = h // 2
    x = center_x - crop_size // 2
    y = center_y - crop_size // 2
    img = img[y:y+crop_size, x:x+crop_size]
    img = cv2.resize(img, (640, 640))
    cv2.imwrite(file_path, img)
    print(f'File successfully saved at {file_path}')
    return file_path

def handle_client(conn, addr, inference_queue):
    print(f'Connected with {addr}')
    try:
        file_path = receive_file(conn, SAVE_DIRECTORY)
        if file_path:
            inference_queue.put((conn, file_path))
        else:
            print("File reception failed.")
    except Exception as e:
        print(f'An error occurred while handling client: {e}')
    finally:
        pass

def inference_worker(inference_queue):
    while True:
        conn, file_path = inference_queue.get()
        try:
            predicted_name = run_inference(file_path)
            predicted_image_path = 'images/pred/predict/' + predicted_name + '.jpg'

            if predicted_image_path and os.path.exists(predicted_image_path):
                predicted_text_path = 'images/pred/predict/labels/' + predicted_name + '.txt'
                send_file(conn, predicted_image_path)

                with open(predicted_text_path, 'r') as file:
                    lines = file.readlines()

                names = {
                    0: 'Belalang', 1: 'Bercak Cokelat', 2: 'Keong', 3: 'Kresek',
                    4: 'Penggerek Batang', 5: 'Penggulung', 6: 'Predator', 7: 'Ulat',
                    8: 'Walang Sangit', 9: 'Wereng'
                }

                detected_objects = []
                for line in lines:
                    box = list(map(float, line.split()))
                    detected_objects.append(names.get(int(box[0])))

                output_string = json.dumps(list(set(detected_objects)))
                text_data = output_string.encode('utf-8')
                text_length = len(text_data)
                conn.sendall(struct.pack('!I', text_length))
                conn.sendall(text_data)
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
