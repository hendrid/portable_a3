import asyncio
import subprocess
import os
import socket
import struct

class DockerInferenceManager:
    def __init__(self, save_directory, docker_image, weights_path):
        self.save_directory = save_directory
        self.docker_image = docker_image
        self.weights_path = weights_path
        self.queue = asyncio.Queue()
        self.container_id = None
        self.is_running = False

    async def start(self):
        command = [
            'sudo', 'docker', 'run', '-d', '--rm', '--ipc=host', '--runtime=nvidia',
            '-v', f'{self.save_directory}:/workspace',
            self.docker_image,
            'sleep', 'infinity'
        ]
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        self.container_id = stdout.decode().strip()
        print(f"Started persistent container with ID: {self.container_id}")

        self.is_running = True
        while self.is_running:
            image_path = await self.queue.get()
            await self.process_image(image_path)
            self.queue.task_done()

    async def process_image(self, image_path):
        print(f'Running YOLOv8 inference on {image_path}...')
        relative_path = os.path.relpath(image_path, self.save_directory)
        command = [
            'sudo', 'docker', 'exec', self.container_id,
            'yolo', 'detect', 'predict',
            f'source=/workspace/{relative_path}',
            f'model={self.weights_path}',
            'project=/workspace/pred',
            'save_txt',
            'exist_ok=True'
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            print(f"YOLOv8 stdout: {stdout.decode()}")
            print(f"YOLOv8 stderr: {stderr.decode()}")
            if process.returncode != 0:
                print(f"YOLOv8 process returned non-zero exit code: {process.returncode}")
                return None
            else:
                print('Inference completed successfully.')
                predicted_path = f'/workspace/pred/predict/{os.path.basename(image_path)}'
                print(f"Predicted image path: {predicted_path}")
                if os.path.exists(os.path.join(self.save_directory, 'pred/predict', os.path.basename(image_path))):
                    print("Predicted image file exists on host system")
                else:
                    print("Predicted image file does not exist on host system")
                return predicted_path
        except Exception as e:
            print(f'Error running YOLOv8 inference: {e}')
        return None

    async def add_image(self, image_path):
        await self.queue.put(image_path)

    async def stop(self):
        self.is_running = False
        if self.container_id:
            command = ['sudo', 'docker', 'stop', self.container_id]
            process = await asyncio.create_subprocess_exec(*command)
            await process.communicate()
            print(f"Stopped container with ID: {self.container_id}")

async def send_file(writer, file_path):
    file_name = os.path.basename(file_path)
    name_bytes = file_name.encode('utf-8')
    name_length = len(name_bytes)

    print(f"Sending file name length: {name_length}")
    writer.write(struct.pack('!I', name_length))
    await writer.drain()

    print(f"Sending file name: {file_name}")
    writer.write(name_bytes)
    await writer.drain()
    
    file_size = os.path.getsize(file_path)
    print(f"Sending file size: {file_size}")
    writer.write(struct.pack('!Q', file_size))
    await writer.drain()
    
    bytes_sent = 0
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
            bytes_sent += len(chunk)
    print(f'Sent file: {file_name}, total bytes sent: {bytes_sent}')

async def receive_file(reader, save_directory):
    name_length_bytes = await reader.readexactly(4)
    name_length = struct.unpack('!I', name_length_bytes)[0]
    print(f"Received file name length: {name_length}")

    file_name_bytes = await reader.readexactly(name_length)
    file_name = file_name_bytes.decode('utf-8')
    print(f"Received file name: {file_name}")

    file_path = os.path.join(save_directory, file_name)
    print(f'Receiving file {file_name}...')

    file_size_bytes = await reader.readexactly(8)
    file_size = struct.unpack('!Q', file_size_bytes)[0]
    print(f"Received file size: {file_size}")

    with open(file_path, 'wb') as f:
        bytes_received = 0
        while bytes_received < file_size:
            chunk = await reader.read(min(4096, file_size - bytes_received))
            if not chunk:
                break
            f.write(chunk)
            bytes_received += len(chunk)

    print(f'File successfully saved at {file_path}, total bytes received: {bytes_received}')
    return file_path

async def handle_client(reader, writer, inference_manager):
    try:
        file_path = await receive_file(reader, inference_manager.save_directory)
        print(f"Received file: {file_path}")

        if file_path:
            await inference_manager.add_image(file_path)
            predicted_image_path = await inference_manager.process_image(file_path)
            print(f"Predicted image path: {predicted_image_path}")

            if predicted_image_path and os.path.exists(predicted_image_path):
                print(f"Sending predicted image: {predicted_image_path}")
                await send_file(writer, predicted_image_path)
                print("Predicted image sent successfully")
            else:
                print("Predicted image not found or inference failed.")
                writer.write(struct.pack('!I', 0))  # Send 0 as name length to indicate failure
                await writer.drain()
        else:
            print("File reception failed.")
            writer.write(struct.pack('!I', 0))  # Send 0 as name length to indicate failure
            await writer.drain()

    except Exception as e:
        print(f'An error occurred in handle_client: {e}')
        writer.write(struct.pack('!I', 0))  # Send 0 as name length to indicate failure
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    save_directory = r'/home/jetson/edge_server/images'
    docker_image = 'ultralytics/ultralytics:latest-jetson-jetpack4'
    weights_path = '/workspace/best_v8n.pt'

    inference_manager = DockerInferenceManager(save_directory, docker_image, weights_path)
    inference_task = asyncio.ensure_future(inference_manager.start())

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, inference_manager),
        '0.0.0.0', 12345)

    addr = server.sockets[0].getsockname()
    print(f'Serving on {addr}')

    try:
        while True:
            await asyncio.sleep(3600)  # Sleep for an hour, then check if we should continue
    except asyncio.CancelledError:
        pass
    finally:
        inference_task.cancel()
        await inference_manager.stop()
        server.close()
        await server.wait_closed()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    main_task = asyncio.ensure_future(main())
    try:
        loop.run_until_complete(main_task)
    except KeyboardInterrupt:
        print("Shutting down...")
        main_task.cancel()
        loop.run_until_complete(asyncio.sleep(0.1))  # Give tasks time to cancel
        loop.run_until_complete(main_task)
    finally:
        loop.close()