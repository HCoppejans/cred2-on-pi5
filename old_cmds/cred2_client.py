#!/usr/bin/env python3
"""client for cred2 remote acquisition"""

import socket
import struct
import json
import os
import sys
import numpy as np

class Cred2Camera:
    """client to trigger captures on raspberry pi"""
    
    def __init__(self, host="192.168.221.11", port=9999):
        self.host = host
        self.port = port

    def set_fps(self, fps):
        """set camera framerate"""
        return self._send_request({"action": "set_fps", "fps": float(fps)})

    def get_status(self):
        """query camera status"""
        return self._send_request({"action": "status"})

    def capture(self, frames=500, fps=None, save_path=None):
        """capture frames and return numpy array"""
        req = {"action": "capture", "frames": frames}
        if fps is not None:
            req["fps"] = float(fps)
            
        resp, data_bytes = self._send_request(req, receive_file=True)
        if resp.get("status") != "ok":
            raise RuntimeError(f"C-RED 2 Capture Error: {resp.get('message')}")

        if save_path:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(data_bytes)

        #skip numpy header and return 3d array
        extracted_frames = len(data_bytes[128:]) // (512 * 640 * 2)
        return np.frombuffer(data_bytes[128:], dtype=np.uint16).reshape((extracted_frames, 512, 640))

    def _send_request(self, req_dict, receive_file=False):
        """send request to server"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))

        req_bytes = json.dumps(req_dict).encode('utf-8')
        s.sendall(struct.pack("!I", len(req_bytes)) + req_bytes)

        hdr_len, file_size = struct.unpack("!IQ", s.recv(12))
        resp_bytes = b""
        while len(resp_bytes) < hdr_len:
            resp_bytes += s.recv(hdr_len - len(resp_bytes))
        resp = json.loads(resp_bytes.decode('utf-8'))

        if not receive_file or file_size == 0:
            s.close()
            return resp

        data_bytes = bytearray(file_size)
        view = memoryview(data_bytes)
        received = 0
        while received < file_size:
            n = s.recv_into(view[received:], file_size - received)
            if n == 0:
                break
            received += n
        s.close()
        return resp, data_bytes

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trigger C-RED 2 Remote Capture")
    parser.add_argument("--frames", type=int, default=500, help="Number of frames (default: 500)")
    parser.add_argument("--fps", type=float, default=500.0, help="Camera framerate (default: 500)")
    parser.add_argument("--output", type=str, default="burst_remote.npy", help="Output .npy file path")
    parser.add_argument("--host", type=str, default="192.168.221.11", help="Pi 5 IP address")
    args = parser.parse_args()

    cam = Cred2Camera(host=args.host)
    print(f"Triggering {args.frames} frames at {args.fps} Hz from C-RED 2 ({args.host})...")
    arr = cam.capture(frames=args.frames, fps=args.fps, save_path=args.output)
    print(f"[SUCCESS] Received array shape {arr.shape} ({arr.dtype}), saved to {args.output}")
