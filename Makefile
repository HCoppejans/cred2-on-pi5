CC ?= gcc
CFLAGS ?= -O3 -Wall -Wextra
LIBS ?= $(shell pkg-config --cflags --libs libusb-1.0 2>/dev/null || echo "-I/usr/include/libusb-1.0 -lusb-1.0")

TARGET = cred2_capture
SRC = cred2_capture.c

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) $(SRC) $(LIBS) -o $(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: all clean
