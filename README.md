# Backyard Birds (BirdStation Node)

This repository is the node-side “BirdStation” runner for Backyard Birds. It records short audio chunks, runs BirdNET analysis, builds a structured detection event, and dispatches the event (for example, over UDP on Wi-Fi).

This README is written to be repeatable from a freshly flashed Raspberry Pi SD card.

---

## Hardware Assumptions

- Raspberry Pi (tested on Pi-class hardware running Debian/Raspberry Pi OS)
- A working microphone input (USB audio interface or supported input device)
- Network connectivity (Wi-Fi or Ethernet) if you want event dispatch off-node

---

## Quick Start (Fresh SD Card)

### 1) Update the OS

sudo apt update
sudo apt full-upgrade -y
sudo reboot

### 2) Install System Dependencies

sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-full \
  alsa-utils \
  usbutils \
  systemd \
  build-essential
sudo apt install -y ffmpeg

### 3) Create a Working Directory and Clone Repositories
This setup expects both repositories in a single parent folder:

mkdir -p ~/birdstation
cd ~/birdstation
git clone https://github.com/kahst/BirdNET-Analyzer.git
git clone https://github.com/rlpickett30/Backyard_Birds.git

### 4) Create and Activate a Virtual Environment and Install Python Requirements
Note: Run the pip install -r requirements.txt command from the correct directory that contains your requirements.txt.
If your requirements.txt is in the Backyard_Birds repo, cd there before running it.

python3 -m venv ~/birdstation/venv
source ~/birdstation/venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt


### 5) Run as a Systemd Service (Recommended)
1) Create the Service File

sudo nano /etc/systemd/system/birdstation-dispatcher.service

Paste the following (update User= if your username is not node0):

[Unit]
Description=BirdStation Dispatcher
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=node0
WorkingDirectory=/home/node0/birdstation/Backyard_Birds

Environment="VIRTUAL_ENV=/home/node0/birdstation/venv"
Environment="PATH=/home/node0/birdstation/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/home/node0/birdstation/venv/bin/python /home/node0/birdstation/Backyard_Birds/scripts/node/dispatcher.py

Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target


2) Enable and Start the Service

sudo systemctl daemon-reload
sudo systemctl enable birdstation-dispatcher.service
sudo systemctl start birdstation-dispatcher.service


3) Verify Status and Follow Logs

systemctl status birdstation-dispatcher.service

journalctl -u birdstation-dispatcher.service -f



What “Success” Looks Like
When functioning correctly, you should see the dispatcher:

Recording audio chunks

Running BirdNET inference

Building a detection event payload (including an event_id)

Dispatching the event (for example, “UDP send successful”)

Troubleshooting
Microphone / Audio Input
List recording devices:

bash
Copy code
arecord -l
If BirdNET is running but detections never appear, confirm that:

The correct input device is selected (if your code supports selection)

The mic is not muted

The recorded .wav chunk is non-empty and contains signal

Service Will Not Start
Check logs:

bash
Copy code
journalctl -u birdstation-dispatcher.service --no-pager -n 200
Common causes:

Wrong User= in the systemd unit

Incorrect paths in WorkingDirectory= or ExecStart=

Virtual environment path mismatch

Missing dependency (system package or Python package)

Directory Layout Expected
text
Copy code
~/birdstation/
  BirdNET-Analyzer/
  Backyard_Birds/
  venv/
Notes for Developers
This project is designed to be repeatable from scratch.

If you change any paths, update the systemd service accordingly.

After editing the systemd unit:

bash
Copy code
sudo systemctl daemon-reload
sudo systemctl restart birdstation-dispatcher.service