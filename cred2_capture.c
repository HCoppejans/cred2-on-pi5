/*c-red 2 usb capture engine*/

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#if defined(__has_include)
#if __has_include(<libusb-1.0/libusb.h>)
#include <libusb-1.0/libusb.h>
#else
#include <libusb.h>
#endif
#else
#include <libusb-1.0/libusb.h>
#endif

#define VID 0x2FAF
#define PID 0x0001
#define EP_IN 0x81

#define WIDTH 640
#define HEIGHT 512
#define PIXELS_PER_FRAME (WIDTH * HEIGHT)  // 327,680 pixels
#define FRAME_BYTES (PIXELS_PER_FRAME * 2) // 655,360 bytes

#define NUM_TRANSFERS 16
#define FRAMES_PER_XFER 2
#define TRANSFER_SIZE (FRAMES_PER_XFER * FRAME_BYTES) // 1.31 mb

static uint8_t *raw_buffer = NULL;
static size_t raw_capacity = 0;
static size_t total_bytes_received = 0;
static size_t target_capture_bytes = 0;
static volatile int stop_acquisition = 0;
static struct libusb_transfer *transfers[NUM_TRANSFERS];

static void LIBUSB_CALL transfer_callback(struct libusb_transfer *xfer) {
  if (xfer->status == LIBUSB_TRANSFER_COMPLETED) {
    if (!stop_acquisition) {
      size_t copy_len = xfer->actual_length;
      if (total_bytes_received + copy_len > raw_capacity) {
        copy_len = raw_capacity - total_bytes_received;
      }
      if (copy_len > 0) {
        memcpy(raw_buffer + total_bytes_received, xfer->buffer, copy_len);
        total_bytes_received += copy_len;
      }

      if (total_bytes_received >= target_capture_bytes) {
        stop_acquisition = 1;
        return;
      }

      // re-submit transfer
      libusb_submit_transfer(xfer);
    }
  }
}

int main(int argc, char **argv) {
  int requested_frames = 500;
  const char *out_path = "burst_capture.npy";

  if (argc >= 2)
    requested_frames = atoi(argv[1]);
  if (argc >= 3)
    out_path = argv[2];

  // allocate buffer with headroom
  int buffer_frames = (int)(requested_frames * 1.15) + 32;
  raw_capacity = (size_t)buffer_frames * FRAME_BYTES;
  target_capture_bytes = (size_t)(requested_frames * 1.12) * FRAME_BYTES;

  printf("Pre-allocating %.1f MB raw DMA buffer for %d frames...\n",
         raw_capacity / 1e6, requested_frames);

  raw_buffer = (uint8_t *)malloc(raw_capacity);
  if (!raw_buffer) {
    fprintf(stderr, "Failed to allocate memory!\n");
    return 1;
  }

  libusb_context *ctx = NULL;
  if (libusb_init(&ctx) < 0) {
    fprintf(stderr, "libusb_init failed\n");
    free(raw_buffer);
    return 1;
  }

  libusb_device_handle *dev = libusb_open_device_with_vid_pid(ctx, VID, PID);
  if (!dev) {
    fprintf(stderr, "C-RED 2 camera not found (VID: 0x%04x, PID: 0x%04x)!\n",
            VID, PID);
    libusb_exit(ctx);
    free(raw_buffer);
    return 1;
  }

  if (libusb_kernel_driver_active(dev, 0)) {
    libusb_detach_kernel_driver(dev, 0);
  }
  libusb_claim_interface(dev, 0);

  // stop prior stream and flush usb fifo
  libusb_control_transfer(dev, 0x40, 0x02, 0, 0, NULL, 0, 500);
  uint8_t trash[16384];
  int transferred = 0;
  for (int i = 0; i < 50; i++) {
    if (libusb_bulk_transfer(dev, EP_IN, trash, sizeof(trash), &transferred,
                             20) != 0 ||
        transferred == 0)
      break;
  }

  // prepare asynchronous hardware queue
  for (int i = 0; i < NUM_TRANSFERS; i++) {
    uint8_t *buf = (uint8_t *)malloc(TRANSFER_SIZE);
    transfers[i] = libusb_alloc_transfer(0);
    libusb_fill_bulk_transfer(transfers[i], dev, EP_IN, buf, TRANSFER_SIZE,
                              transfer_callback, NULL, 5000);
    libusb_submit_transfer(transfers[i]);
  }

  // start camera acquisition
  printf("Starting high-speed stream...\n");
  struct timespec t_start, t_end;
  clock_gettime(CLOCK_MONOTONIC, &t_start);
  libusb_control_transfer(dev, 0x40, 0x01, 0, 0, NULL, 0, 1000);

  // pump event loop
  while (!stop_acquisition) {
    libusb_handle_events_completed(ctx, NULL);
  }
  clock_gettime(CLOCK_MONOTONIC, &t_end);

  // stop camera acquisition
  libusb_control_transfer(dev, 0x40, 0x02, 0, 0, NULL, 0, 1000);

  double elapsed =
      (t_end.tv_sec - t_start.tv_sec) + (t_end.tv_nsec - t_start.tv_nsec) / 1e9;
  double fps = (total_bytes_received / (double)FRAME_BYTES) / elapsed;
  printf("\n[SUCCESS] Streamed %.1f MB in %.3f s (%.1f fps)\n",
         total_bytes_received / 1e6, elapsed, fps);

  // clean up usb transfers
  for (int i = 0; i < NUM_TRANSFERS; i++) {
    libusb_cancel_transfer(transfers[i]);
  }
  struct timeval tv = {0, 50000};
  libusb_handle_events_timeout_completed(ctx, &tv, NULL);
  for (int i = 0; i < NUM_TRANSFERS; i++) {
    free(transfers[i]->buffer);
    libusb_free_transfer(transfers[i]);
  }

  // extract frames using hardware tag
  printf("Extracting frames via hardware tag...\n");
  uint16_t *raw_u16 = (uint16_t *)raw_buffer;
  size_t total_u16 = total_bytes_received / 2;

  uint8_t *clean_buffer =
      (uint8_t *)malloc((size_t)requested_frames * FRAME_BYTES);
  if (!clean_buffer) {
    fprintf(stderr, "Failed to allocate clean output buffer!\n");
    libusb_release_interface(dev, 0);
    libusb_close(dev);
    libusb_exit(ctx);
    free(raw_buffer);
    return 1;
  }

  int extracted = 0;
  uint32_t first_id = 0, last_id = 0;
  int drop_events = 0;
  int total_dropped = 0;

  size_t p = 0;
  while (p + PIXELS_PER_FRAME <= total_u16 && extracted < requested_frames) {
    // look for c-red 2 tag: pixel 2 == 0 and pixel 3 has tag mask 0x3ff8
    // (16376)
    if (raw_u16[p + 2] == 0 && (raw_u16[p + 3] & 0x3FF8) == 0x3FF8) {
      uint32_t fid =
          ((uint32_t)raw_u16[p]) | (((uint32_t)raw_u16[p + 1]) << 16);

      if (extracted == 0) {
        first_id = fid;
      } else {
        int32_t diff = (int32_t)(fid - last_id);
        if (diff != 1) {
          drop_events++;
          if (diff > 1)
            total_dropped += (diff - 1);
          if (drop_events <= 5) {
            printf("  Drop detected: ID %u -> %u (+%d)\n", last_id, fid, diff);
          }
        }
      }
      last_id = fid;

      // copy full frame
      memcpy(clean_buffer + (size_t)extracted * FRAME_BYTES, &raw_u16[p],
             FRAME_BYTES);
      extracted++;

      // jump forward by full frame
      p += PIXELS_PER_FRAME;
    } else {
      // scan forward 1 pixel to re-lock
      p++;
    }
  }

  printf("\n--- Quality Report ---\n");
  printf("First Frame ID:    %u\n", first_id);
  printf("Last Frame ID:     %u\n", last_id);
  printf("Extracted Frames:  %d / %d\n", extracted, requested_frames);
  printf("Drop Events:       %d\n", drop_events);
  printf("Dropped Frames:    %d\n", total_dropped);

  // save clean frames as numpy .npy file
  FILE *fp = fopen(out_path, "wb");
  if (fp) {
    char header_str[128];
    snprintf(
        header_str, sizeof(header_str),
        "{'descr': '<u2', 'fortran_order': False, 'shape': (%d, %d, %d), }",
        extracted, HEIGHT, WIDTH);
    int hlen = strlen(header_str);
    int pad = 64 - ((10 + hlen + 1) % 64);
    int total_hlen = hlen + pad + 1;

    uint8_t magic[10] = {0x93,
                         'N',
                         'U',
                         'M',
                         'P',
                         'Y',
                         0x01,
                         0x00,
                         (uint8_t)(total_hlen & 0xFF),
                         (uint8_t)((total_hlen >> 8) & 0xFF)};
    fwrite(magic, 1, 10, fp);
    fwrite(header_str, 1, hlen, fp);
    for (int i = 0; i < pad; i++)
      fputc(' ', fp);
    fputc('\n', fp);

    fwrite(clean_buffer, 1, (size_t)extracted * FRAME_BYTES, fp);
    fclose(fp);
    printf("[COMPLETE] Saved clean dataset to %s\n", out_path);
  } else {
    fprintf(stderr, "Failed to open output path %s for writing!\n", out_path);
  }

  libusb_release_interface(dev, 0);
  libusb_close(dev);
  libusb_exit(ctx);
  free(raw_buffer);
  free(clean_buffer);
  return 0;
}
