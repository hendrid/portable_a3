import socket
import os
import sys
import struct

# Directory containing the image files
DIRECTORY = '/Users/hendri/Documents/PROJECTS/portable_a3/images'  # Update with the correct directory
SERVER_IP = '192.168.100.212'  # Change to your server IP
SERVER_PORT = 12345

def send_file():
    file_name = 'hama.jpg'
    file_path = os.path.join(DIRECTORY, file_name)
    
    if not os.path.exists(file_path):
        print(f"File {file_name} not found in {DIRECTORY}. Exiting program.")
        sys.exit(1)
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print(f'Connected to server at {SERVER_IP}:{SERVER_PORT}')
            print(f'Sending file {file_name}...')
            
            # Send file name length
            name_bytes = file_name.encode('utf-8')
            client_socket.send(struct.pack('!I', len(name_bytes)))
            print(f"Sent file name length: {len(name_bytes)}")
            
            # Send file name
            client_socket.send(name_bytes)
            print(f"Sent file name: {file_name}")
            
            # Send file size
            file_size = os.path.getsize(file_path)
            client_socket.send(struct.pack('!Q', file_size))
            print(f"Sent file size: {file_size}")
            
            # Send file content
            bytes_sent = 0
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
            print(f'File content sent successfully. Total bytes sent: {bytes_sent}')
            
            # Receive predicted image name length
            name_length_bytes = client_socket.recv(4)
            if not name_length_bytes:
                print("Did not receive name length from server.")
                return
            name_length = struct.unpack('!I', name_length_bytes)[0]
            print(f"Received name length: {name_length}")
            
            if name_length == 0:
                print("Server failed to process the image.")
                return
            
            # Receive predicted image name
            predicted_file_name = client_socket.recv(name_length).decode('utf-8')
            print(f'Receiving predicted image: {predicted_file_name}')
            
            # Receive file size
            file_size_bytes = client_socket.recv(8)
            if not file_size_bytes:
                print("Did not receive file size from server.")
                return
            file_size = struct.unpack('!Q', file_size_bytes)[0]
            print(f"Received file size: {file_size}")
            
            predicted_file_path = os.path.join(DIRECTORY, 'predicted_' + predicted_file_name)
            with open(predicted_file_path, 'wb') as f:
                bytes_received = 0
                while bytes_received < file_size:
                    chunk = client_socket.recv(min(4096, file_size - bytes_received))
                    if not chunk:
                        print(f"Connection closed after receiving {bytes_received} bytes")
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
                print(f"Received {bytes_received} bytes")
            
            if bytes_received == file_size:
                print(f'Predicted image saved at: {predicted_file_path}')
            else:
                print(f"Warning: Received {bytes_received} bytes, expected {file_size} bytes")
    
    except ConnectionRefusedError:
        print(f"Could not connect to server at {SERVER_IP}:{SERVER_PORT}. Is the server running?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    send_file()