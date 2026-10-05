#!/usr/bin/env python3
import sys
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 115200

with serial.Serial(PORT, BAUD, timeout=1) as s:
    s.reset_input_buffer()

    if len(sys.argv) > 1:
        # Input is in microseconds (µs), converted to seconds for fli-cli
        target_us = float(sys.argv[1])
        target_s = target_us * 1e-6

        cmd = f"set tint {target_s:.9f}\ntint\n"
        s.write(cmd.encode('ascii'))
        time.sleep(0.1)
        print(f"Applying {target_us} µs ({target_s:.9f} s)...")
    else:
        s.write(b"tint\n")
        time.sleep(0.05)
        print("Reading current camera settings...")

    resp = s.read(400).decode('latin1', errors='ignore')
    for line in resp.splitlines():
        line = line.strip()
        if line and not line.startswith("fli-cli>"):
            print(f"  {line}")
