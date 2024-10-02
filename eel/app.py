import eel
import socket
import os
import base64
import struct
import time
from collections import Counter
import ast

# Configuration
DIRECTORY = '/Users/hendri/Documents/PROJECTS/portable_a3/eel/web/images'
# SERVER_IP = '192.168.100.212'
SERVER_IP = '10.252.133.225'
SERVER_PORT = 12345
BUFFER_SIZE = 4096

@eel.expose
def process_image(base64String):
    file_bytes = base64.b64decode(base64String.split(',')[1])
    file_name = f"{int(time.time())}.jpg"
    file_path = os.path.join(DIRECTORY, file_name)
    
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((SERVER_IP, SERVER_PORT))
            send_file(client_socket, file_path)
            
            try:
                received_file_path = receive_file(client_socket, DIRECTORY)
                received_text = receive_text(client_socket)
                received_text = ast.literal_eval(received_text)
                received_text = list(set(received_text))

                object_count = Counter(received_text)
                output_string = ', '.join(f'{count} {obj}' for obj, count in object_count.items())

                print(received_file_path)
                print(output_string)
                print(received_text)
                return [received_file_path, output_string, received_text]
                # return f'{received_file_path}, {received_text}'
            except ConnectionError as e:
                return f"Error receiving file or text: {e}"
            except struct.error:
                return "Received invalid data from server. The inference might have failed."
    
    except ConnectionRefusedError:
        return f"Could not connect to server at {SERVER_IP}:{SERVER_PORT}. Is the server running?"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

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

def receive_file(conn, save_directory):
    name_length = struct.unpack('!I', conn.recv(4))[0]
    file_name = conn.recv(name_length).decode('utf-8')
    file_path = os.path.join(save_directory, 'predicted_' + file_name)
    file_size = struct.unpack('!Q', conn.recv(8))[0]

    with open(file_path, 'wb') as f:
        remaining = file_size
        while remaining > 0:
            chunk_size = BUFFER_SIZE if remaining > BUFFER_SIZE else remaining
            chunk = conn.recv(chunk_size)
            if not chunk:
                raise ConnectionError("Connection closed while receiving file")
            f.write(chunk)
            remaining -= len(chunk)

    return file_path

def receive_text(conn):
    text_length = struct.unpack('!I', conn.recv(4))[0]
    text = conn.recv(text_length).decode('utf-8')
    return text

eel.init('web')
eel.start('index.html', size=(600, 1024))