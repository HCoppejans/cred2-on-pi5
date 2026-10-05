#!/usr/bin/env python3
import time
import sys
import numpy as np
import usb.core
import usb.util

VID = 0x2FAF
PID = 0x0001
EP_IN = 0x81

WIDTH = 640
HEIGHT = 512
FRAME_BYTES = WIDTH * HEIGHT * 2    #655,360 bytes
CHUNK_FRAMES = 20                   #20 frames = 13.1 mb
CHUNK_BYTES = CHUNK_FRAMES * FRAME_BYTES
NUM_CHUNKS = 15                     #15 chunks x 20 frames = 300 frames
TOTAL_FRAMES = CHUNK_FRAMES * NUM_CHUNKS

print(f"Searching for C-RED 2 (VID: {VID:#06x}, PID: {PID:#06x})...")
dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    print("[ERROR] C-RED 2 not found!")
    sys.exit(1)

#detach kernel driver if active
try:
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
except Exception:
    pass

#claim interface 0
usb.util.claim_interface(dev, 0)

try:
    #stop prior stream and flush usb fifo
    try:
        dev.ctrl_transfer(0x40, 0x02, 0, 0, timeout=500)
    except Exception:
        pass
    
    while True:
        try:
            dev.read(EP_IN, 16384, timeout=50)
        except Exception:
            break

    #pre-allocate pyusb dma buffers
    print(f"Pre-allocating {NUM_CHUNKS} buffers ({CHUNK_BYTES / 1e6:.1f} MB each, total {TOTAL_FRAMES} frames)...")
    buffers = [usb.util.create_buffer(CHUNK_BYTES) for _ in range(NUM_CHUNKS)]

    #start acquisition
    print("Starting acquisition...")
    dev.ctrl_transfer(0x40, 0x01, 0, 0, timeout=1000)
    time.sleep(0.05)

    #capture burst
    print(f"Capturing continuous burst of {TOTAL_FRAMES} frames ({TOTAL_FRAMES * FRAME_BYTES / 1e6:.1f} MB)...")
    t_start = time.perf_counter()

    for i in range(NUM_CHUNKS):
        dev.read(EP_IN, buffers[i], timeout=3000)

    t_end = time.perf_counter()
    elapsed = t_end - t_start
    actual_fps = TOTAL_FRAMES / elapsed
    print(f"\n[SUCCESS] Captured {TOTAL_FRAMES} frames in {elapsed:.3f} s ({actual_fps:.1f} fps)")

    #stop camera
    print("Stopping camera acquisition...")
    dev.ctrl_transfer(0x40, 0x02, 0, 0, timeout=1000)

    #unpack into numpy array
    print("Unpacking raw buffers into NumPy array...")
    data = np.empty((TOTAL_FRAMES, HEIGHT, WIDTH), dtype=np.uint16)
    for i, buf in enumerate(buffers):
        start = i * CHUNK_FRAMES
        end = start + CHUNK_FRAMES
        data[start:end] = np.frombuffer(buf, dtype=np.uint16).reshape((CHUNK_FRAMES, HEIGHT, WIDTH))

    #integrity check
    fids = [int(data[i, 0, 0]) | (int(data[i, 0, 1]) << 16) for i in range(TOTAL_FRAMES)]
    diffs = np.diff(fids)
    drops = np.where(diffs > 1)[0]
    total_dropped = int(np.sum(diffs[drops] - 1)) if len(drops) > 0 else 0

    print(f"First Frame ID: {fids[0]}")
    print(f"Last Frame ID:  {fids[-1]}")
    print(f"Drop Points:    {len(drops)}")
    print(f"Dropped Frames: {total_dropped}")

    #save
    save_path = "/home/eltdev/cred2/data/burst_capture.npy"
    print(f"Saving to {save_path}...")
    np.save(save_path, data)
    print("Save complete!")

finally:
    try:
        usb.util.release_interface(dev, 0)
    except Exception:
        pass
    print("Cleanup complete.")
