#!/usr/bin/env python3
"""send shutdown command to cred2"""

import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 115200

with serial.Serial(PORT, BAUD, timeout=1) as s:
    s.reset_input_buffer()
    print("Sending shutdown command to C-RED 2...")
    s.write(b"shutdown\n")
    time.sleep(0.5)

    resp = s.read(400).decode('latin1', errors='ignore')
    for line in resp.splitlines():
        line = line.strip()
        if line and not line.startswith("fli-cli>"):
            print(f"  {line}")
    print("Done.")
