#!/usr/bin/env python3
import sys
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 115200

with serial.Serial(PORT, BAUD, timeout=1) as s:
    s.reset_input_buffer()

    if len(sys.argv) > 1:
        # target_fps = float(sys.argv[1])
        cmd = f"set sensitivity low\n"
        s.write(cmd.encode('ascii'))
        time.sleep(0.1)
        print(f"Applying sensitivity medium")
    else:
        s.write(b"sensitivity\n")
        time.sleep(0.05)
        print("Reading current camera settings...")

    resp = s.read(400).decode('latin1', errors='ignore')
    for line in resp.splitlines():
        line = line.strip()
        if line and not line.startswith("fli-cli>"):
            print(f"  {line}")
