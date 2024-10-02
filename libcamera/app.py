import eel
import subprocess

eel.init('web')  # 'web' is the directory containing your HTML/JS/CSS

@eel.expose
def capture_image():
    try:
        # Use libcamera-still to capture an image
        subprocess.run(['libcamera-still', '-o', 'captured_image.jpg'], check=True)
        return 'captured_image.jpg'
    except subprocess.CalledProcessError:
        return None

eel.start('index.html', size=(300, 200))