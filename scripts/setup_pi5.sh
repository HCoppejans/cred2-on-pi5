#!/bin/bash
set -e

echo "=== Setting up Raspberry Pi 5 for C-RED 2 Acquisition ==="

#system packages
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev libusb-1.0-0 libusb-1.0-0-dev git build-essential

#permissions
sudo usermod -a -G dialout,plugdev $USER
sudo cp ../udev/99-cred2.rules /etc/udev/rules.d/ 2>/dev/null || sudo cp udev/99-cred2.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

#usb dma parameters
echo 256 | sudo tee /sys/module/usbcore/parameters/usbfs_memory_mb
echo "options usbcore usbfs_memory_mb=256" | sudo tee /etc/modprobe.d/usbcore.conf
if [ -f /boot/firmware/cmdline.txt ]; then
    sudo sed -i 's/$/ usbcore.usbfs_memory_mb=256/' /boot/firmware/cmdline.txt
fi

#cpu governor
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

#build c engine
cd "$(dirname "$0")/.."
make clean && make

echo "=== Setup complete! ==="
