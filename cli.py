#!/usr/bin/env python3
"""simple cli for cred2"""

import os
import sys
import time
import serial

PORT = os.environ.get("CRED2_PORT", "/dev/ttyACM0")
BAUD = 115200


def send_command(ser: serial.Serial, cmd: str) -> str:
    """send command to camera and return response"""
    ser.reset_input_buffer()
    ser.write((cmd.strip() + "\n").encode("ascii"))
    time.sleep(0.08)

    timeout = 3.0 if "shutdown" in cmd.lower() else 1.5
    resp = b""
    start = time.time()
    while time.time() - start < timeout:
        in_wait = getattr(ser, "in_waiting", 0)
        chunk = ser.read(max(in_wait, 1024))
        if chunk:
            resp += chunk
            if b"fli-cli>" in chunk:
                break
        else:
            time.sleep(0.02)

    lines = []
    for line in resp.decode("latin1", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("fli-cli>"):
            lines.append(line)
    return "\n".join(lines)


def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.2)
    except serial.SerialException as e:
        print(f"Error opening {PORT}: {e}", file=sys.stderr)
        sys.exit(1)

    with ser:
        #if command-line arguments are provided, send that single command
        if len(sys.argv) > 1:
            cmd = " ".join(sys.argv[1:])
            out = send_command(ser, cmd)
            if out:
                print(out)
        else:
            while True:
                cmd = input("cred2> ").strip()
                if cmd:
                    out = send_command(ser, cmd)
                    if out:
                        print(out)


if __name__ == "__main__":
    main()
