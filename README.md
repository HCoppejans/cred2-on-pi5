# C-RED 2 Setup & Acquisition

Tools to configure and acquire data from the First Light Imaging C-RED 2 camera on a Raspberry Pi 5.

For the pi5, run this script to setup the hardware:
```bash
./scripts/setup_pi5.sh
```
other devices might not need all of the optimisations

## Building

Compile the C capture binary (`cred2_capture`):
```bash
make
```

## Running the Scripts

### Camera Serial CLI (`cli.py`)
Send commands to the camera over `/dev/ttyACM0`:
```bash
#single commands:
./cli.py temperatures
./cli.py set fps 500
./cli.py tint
./cli.py shutdown

#interactive session (press ctrl+c to exit):
./cli.py
```

### Local Capture (`cred2_capture`)
Capture frames directly on the Pi to a NumPy array (`.npy`):
```bash
#usage: ./cred2_capture <num_frames> <output_path>
./cred2_capture 500 /mnt/nvme/cred2_data/burst_500hz.npy
```
This works for my pi5, since I have an nvme.

### Remote Acquisition Server (`cred2_server.py`)
Runs on the Pi to allow workstations to trigger captures over TCP (port 9999):
```bash
python3 cred2_server.py
```
To run as a systemd service:
```bash
sudo cp cred2-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cred2-server.service
```

### View the data
Inspect recorded `.npy` files:
```bash
python3 view.py burst.npy        #simple viewer (arrow keys / slider)
```
