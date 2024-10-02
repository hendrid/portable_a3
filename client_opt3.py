import socket
import os
import sys
import struct

# Configuration
DIRECTORY = '/Users/hendri/Documents/PROJECTS/portable_a3/images'  
SERVER_IP = '192.168.173.52'
SERVER_PORT = 12345
BUFFER_SIZE = 4096

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
    file_path = os.path.join(save_directory, 'predicted_' + file_name)

    # Receive file size
    file_size = struct.unpack('!Q', conn.recv(8))[0]

    print(f'Receiving file: {file_name}, Size: {file_size} bytes')

    # Receive and save the file
    with open(file_path, 'wb') as f:
        remaining = file_size
        while remaining > 0:
            chunk_size = BUFFER_SIZE if remaining > BUFFER_SIZE else remaining
            chunk = conn.recv(chunk_size)
            if not chunk:
                raise ConnectionError("Connection closed while receiving file")
            f.write(chunk)
            remaining -= len(chunk)

    print(f'File successfully saved at {file_path}')
    return file_path

def process_image():
    file_name = 'hama2.jpg'  # You can modify this to allow user input or iterate through multiple files
    file_path = os.path.join(DIRECTORY, file_name)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"File {file_name} not found in {DIRECTORY}. Exiting program.")
        sys.exit(1)
    
    try:
        # Establish connection to the server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print(f'Connected to server. Processing file {file_name}...')
            
            # Send the file
            send_file(client_socket, file_path)
            
            # Receive the processed file
            try:
                received_file_path = receive_file(client_socket, DIRECTORY)
                print(f'Processed image saved at: {received_file_path}')
            except ConnectionError as e:
                print(f"Error receiving file: {e}")
            except struct.error:
                print("Received invalid data from server. The inference might have failed.")
    
    except ConnectionRefusedError:
        print(f"Could not connect to server at {SERVER_IP}:{SERVER_PORT}. Is the server running?")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    process_image()