# USB Fingerprint Reader SDK - Makefile
# =====================================

CC = gcc
CFLAGS = -Wall -Wextra -O2 -I./include
LDFLAGS = -lusb-1.0 -lm -lz

# macOS specific (Homebrew libusb)
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
    CFLAGS += -I/opt/homebrew/include
    LDFLAGS += -L/opt/homebrew/lib
endif

# Linux specific
ifeq ($(UNAME_S),Linux)
    CFLAGS += $(shell pkg-config --cflags libusb-1.0 2>/dev/null)
    LDFLAGS += $(shell pkg-config --libs libusb-1.0 2>/dev/null)
endif

# Source files
SRC_DIR = src
SRCS = $(SRC_DIR)/fingerprint.c $(SRC_DIR)/main.c
OBJS = $(SRCS:.c=.o)

# Output
TARGET = fingerprint

# Library output
LIB_SRCS = $(SRC_DIR)/fingerprint.c
LIB_OBJS = $(LIB_SRCS:.c=.o)
LIB_STATIC = libfingerprint.a
LIB_SHARED = libfingerprint.so
ifeq ($(UNAME_S),Darwin)
    LIB_SHARED = libfingerprint.dylib
endif

# Default target
all: $(TARGET)

# Build CLI executable
$(TARGET): $(OBJS)
	$(CC) $(OBJS) -o $(TARGET) $(LDFLAGS)

# Compile source files
%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

# Build static library
static: $(LIB_OBJS)
	ar rcs $(LIB_STATIC) $(LIB_OBJS)

# Build shared library
shared: CFLAGS += -fPIC
shared: $(LIB_OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) -shared -o $(LIB_SHARED) $(LIB_OBJS) $(LDFLAGS)
else
	$(CC) -shared -o $(LIB_SHARED) $(LIB_OBJS) $(LDFLAGS)
endif

# Build all libraries
libs: static shared

# Install (requires sudo)
install: $(TARGET) static shared
	install -d /usr/local/bin
	install -d /usr/local/lib
	install -d /usr/local/include
	install -m 755 $(TARGET) /usr/local/bin/
	install -m 644 $(LIB_STATIC) /usr/local/lib/
	install -m 755 $(LIB_SHARED) /usr/local/lib/
	install -m 644 include/fingerprint.h /usr/local/include/
ifeq ($(UNAME_S),Linux)
	ldconfig
endif

# Uninstall
uninstall:
	rm -f /usr/local/bin/$(TARGET)
	rm -f /usr/local/lib/$(LIB_STATIC)
	rm -f /usr/local/lib/$(LIB_SHARED)
	rm -f /usr/local/include/fingerprint.h

# Clean
clean:
	rm -f $(OBJS) $(TARGET) $(LIB_STATIC) $(LIB_SHARED)

# Debug build
debug: CFLAGS += -g -DDEBUG
debug: $(TARGET)

# Help
help:
	@echo "USB Fingerprint Reader SDK - Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build CLI executable (default)"
	@echo "  static   - Build static library (libfingerprint.a)"
	@echo "  shared   - Build shared library (libfingerprint.so/dylib)"
	@echo "  libs     - Build both static and shared libraries"
	@echo "  install  - Install binary and libraries (requires sudo)"
	@echo "  uninstall- Remove installed files (requires sudo)"
	@echo "  clean    - Remove build artifacts"
	@echo "  debug    - Build with debug symbols"
	@echo "  help     - Show this help"
	@echo ""
	@echo "Usage:"
	@echo "  make           # Build CLI tool"
	@echo "  make libs      # Build libraries"
	@echo "  sudo make install"

.PHONY: all static shared libs install uninstall clean debug help
