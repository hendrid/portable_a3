#!/bin/bash
echo "jetson" | sudo -S su
cd edge_server
sudo python3 server_opt3.py &
python3 show_ip.py