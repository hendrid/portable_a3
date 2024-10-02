import socket
import os
import sys

# Directory containing the image files
DIRECTORY = '/Users/hendri/Documents/PROJECTS/portable_a3/images'  # Update with the correct directory
SERVER_IP = '192.168.100.212'  # Change to your server IP
SERVER_PORT = 12345

def send_file():
    file_name = 'hama.jpg'
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
            
            # Send the file content
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096)  # Increased buffer size
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
            
            print('File successfully sent.')
    
    except ConnectionRefusedError:
        print(f"Could not connect to server at {SERVER_IP}:{SERVER_PORT}. Is the server running?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    send_file()
