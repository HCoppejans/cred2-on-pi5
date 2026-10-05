#!/usr/bin/env python3
"""frame viewer for cred2 .npy files"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

if len(sys.argv) < 2:
    print("Usage: python3 view.py <filename.npy>")
    sys.exit(1)

#load data
data = np.load(sys.argv[1]).astype(np.float32)
num_frames = data.shape[0]

#mask first 4 pixels (hardware tags)
data[:, 0, :4] = np.median(data[0])

#contrast scaling
vmin = float(np.percentile(data[0], 1))
vmax = float(np.percentile(data[0], 99))

fig, ax = plt.subplots(figsize=(8, 7))
plt.subplots_adjust(bottom=0.15)

im = ax.imshow(data[0], cmap='inferno', vmin=vmin, vmax=vmax)
title = ax.set_title(f"Frame 0 / {num_frames - 1}")
plt.colorbar(im, ax=ax)

#frame slider at bottom
ax_slider = plt.axes([0.15, 0.05, 0.7, 0.04])
slider = Slider(ax_slider, 'Frame', 0, num_frames - 1, valinit=0, valstep=1)

def update(val):
    idx = int(slider.val)
    im.set_data(data[idx])
    title.set_text(f"Frame {idx} / {num_frames - 1}")
    fig.canvas.draw_idle()

slider.on_changed(update)

#cycle with keyboard: left / right arrow keys
def on_key(event):
    if event.key in ['right', 'up'] and slider.val < num_frames - 1:
        slider.set_val(slider.val + 1)
    elif event.key in ['left', 'down'] and slider.val > 0:
        slider.set_val(slider.val - 1)

fig.canvas.mpl_connect('key_press_event', on_key)

plt.show()
