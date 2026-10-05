#!/usr/bin/env python3
"""set target temperature or read telemetry"""

import sys
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 115200


def send_and_read(ser: serial.Serial, cmd: str) -> list[str]:
    ser.reset_input_buffer()
    ser.write((cmd + "\n").encode('ascii'))
    time.sleep(0.15)
    
    resp = b""
    while True:
        chunk = ser.read(2048)
        if not chunk:
            break
        resp += chunk
        if b"fli-cli>" in chunk:
            break

    lines = []
    for line in resp.decode('latin1', errors='ignore').splitlines():
        line = line.strip()
        if line and not line.startswith("fli-cli>"):
            lines.append(line)
    return lines


with serial.Serial(PORT, BAUD, timeout=0.5) as s:
    if len(sys.argv) > 1:
        target_temp = float(sys.argv[1])
        print(f"Applying sensor target: {target_temp:.1f} °C...")
        send_and_read(s, f"set temperatures sensor {target_temp:.1f}")
        time.sleep(0.1)

    print("Current telemetry:")
    for line in send_and_read(s, "temperatures"):
        print(f"  {line}")
    for line in send_and_read(s, "power"):
        print(f"  Power (A:V:W): {line}")
