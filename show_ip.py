# save this as show_ip.py
import os
import socket
import tkinter as tk

def get_ip_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def show_ip():
    ip = get_ip_address()
    root = tk.Tk()
    root.title("IP Address")
    label = tk.Label(root, text=f"Current IP Address: {ip}")
    label.pack(padx=20, pady=20)
    root.mainloop()

if __name__ == "__main__":
    show_ip()
