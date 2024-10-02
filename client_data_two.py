import socket
import os
import sys
import struct

# Directory containing the image files
DIRECTORY = '/Users/hendri/Documents/PROJECTS/portable_a3/images'  # Update with the correct directory
SERVER_IP = '192.168.100.212'  # Change to your server IP
SERVER_PORT = 12345

def send_file():
    file_name = 'hama2.jpg'
    file_path = os.path.join(DIRECTORY, file_name)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"File {file_name} not found in {DIRECTORY}. Exiting program.")
        sys.exit(1)
    
    try:
        # Establish connection to the server
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((SERVER_IP, SERVER_PORT))
            print(f'Sending file {file_name}...')
            
            # Send the file name
            client_socket.send(file_name.encode())
            
            # Send the file size
            file_size = os.path.getsize(file_path)
            client_socket.send(struct.pack('!Q', file_size))
            
            # Send the file content
            with open(file_path, 'rb') as f:
                bytes_sent = 0
                while bytes_sent < file_size:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
            
            print('File successfully sent.')
            
            # Receive the predicted image
            predicted_file_name = client_socket.recv(1024).decode('utf-8', errors='ignore').strip()
            
            if predicted_file_name == "INFERENCE_FAILED":
                print("Server failed to process the image.")
                return
            
            print(f'Receiving predicted image: {predicted_file_name}')
            
            # Receive the file size
            file_size = struct.unpack('!Q', client_socket.recv(8))[0]
            
            predicted_file_path = os.path.join(DIRECTORY, 'predicted_' + predicted_file_name)
            with open(predicted_file_path, 'wb') as f:
                bytes_received = 0
                while bytes_received < file_size:
                    chunk = client_socket.recv(min(4096, file_size - bytes_received))
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)
            
            print(f'Predicted image saved at: {predicted_file_path}')
    
    except ConnectionRefusedError:
        print(f"Could not connect to server at {SERVER_IP}:{SERVER_PORT}. Is the server running?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    send_file()