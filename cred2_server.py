#!/usr/bin/env python3
"""remote acquisition daemon for cred2"""

import socket
import struct
import json
import os
import time
import subprocess
import threading
import serial

PORT = 9999
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = os.path.join(SCRIPT_DIR, "cred2_capture")

#nvme storage preferred, fallback to local directory
if os.path.exists("/mnt/nvme/cred2_data"):
    TEMP_FILE = "/mnt/nvme/cred2_data/remote_burst.npy"
else:
    TEMP_FILE = os.path.join(SCRIPT_DIR, "data", "remote_burst.npy")

SERIAL_PORT = "/dev/ttyACM0"
current_configured_fps = None

def apply_camera_settings(target_fps=None):
    global current_configured_fps
    try:
        with serial.Serial(SERIAL_PORT, 115200, timeout=1) as s:
            s.reset_input_buffer()
            cmd = "set imagetags on\n"
            if target_fps is not None and target_fps != current_configured_fps:
                cmd += f"set fps {target_fps}\n"
            s.write(cmd.encode('ascii'))
            time.sleep(0.05)
            resp = s.read(300).decode('latin1', errors='ignore')
            if target_fps is not None:
                current_configured_fps = target_fps
            return True, resp
    except Exception as e:
        return False, str(e)

def handle_client(conn, addr):
    try:
        header_len_data = conn.recv(4)
        if not header_len_data:
            return
        req_len = struct.unpack("!I", header_len_data)[0]
        req_bytes = b""
        while len(req_bytes) < req_len:
            chunk = conn.recv(min(4096, req_len - len(req_bytes)))
            if not chunk:
                break
            req_bytes += chunk

        req = json.loads(req_bytes.decode('utf-8'))
        action = req.get("action", "capture")
        target_fps = req.get("fps", None)

        #action: set_fps only
        if action == "set_fps":
            ok, resp = apply_camera_settings(target_fps)
            resp_hdr = json.dumps({"status": "ok" if ok else "error", "message": resp, "fps": current_configured_fps}).encode('utf-8')
            conn.sendall(struct.pack("!IQ", len(resp_hdr), 0) + resp_hdr)
            return

        #action: query camera status
        if action == "status":
            try:
                with serial.Serial(SERIAL_PORT, 115200, timeout=1) as s:
                    s.write(b"fps\ntint\nstatus\n")
                    time.sleep(0.05)
                    raw_status = s.read(400).decode('latin1', errors='ignore')
                resp_hdr = json.dumps({"status": "ok", "info": raw_status}).encode('utf-8')
            except Exception as e:
                resp_hdr = json.dumps({"status": "error", "message": str(e)}).encode('utf-8')
            conn.sendall(struct.pack("!IQ", len(resp_hdr), 0) + resp_hdr)
            return

        #action: capture (with optional fps change)
        frames = req.get("frames", 500)
        if target_fps is not None:
            apply_camera_settings(target_fps)

        os.makedirs(os.path.dirname(TEMP_FILE), exist_ok=True)
        cmd = [BIN_PATH, str(frames), TEMP_FILE]
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0 or not os.path.exists(TEMP_FILE):
            err_msg = res.stderr.strip() if res.stderr else "Capture failed"
            resp_hdr = json.dumps({"status": "error", "message": err_msg}).encode('utf-8')
            conn.sendall(struct.pack("!IQ", len(resp_hdr), 0) + resp_hdr)
            return

        file_size = os.path.getsize(TEMP_FILE)
        resp_hdr = json.dumps({
            "status": "ok",
            "frames": frames,
            "fps": current_configured_fps,
            "size_bytes": file_size
        }).encode('utf-8')

        #send response header + file contents (zero-copy sendfile)
        conn.sendall(struct.pack("!IQ", len(resp_hdr), file_size) + resp_hdr)
        with open(TEMP_FILE, "rb") as f:
            conn.sendfile(f)

    except Exception as e:
        print(f"Error handling {addr}: {e}")
    finally:
        conn.close()

def main():
    apply_camera_settings()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)
    print(f"[C-RED 2 Server] Listening on 0.0.0.0:{PORT}...")

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()
