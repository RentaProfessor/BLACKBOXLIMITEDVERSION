#!/bin/bash

# BLACK BOX - Swap file setup script for NVIDIA Jetson Orin Nano
# Creates 16GB swap file on NVMe for optimal performance

set -e

SWAP_SIZE="16G"
SWAP_FILE="/mnt/nvme/swapfile"
NVME_MOUNT="/mnt/nvme"

echo "BLACK BOX - Setting up swap file..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check if NVMe is mounted
if ! mountpoint -q "$NVME_MOUNT"; then
    echo "Error: NVMe not mounted at $NVME_MOUNT"
    echo "Please mount your NVMe drive first"
    exit 1
fi

# Check available space
AVAILABLE_SPACE=$(df "$NVME_MOUNT" | awk 'NR==2 {print $4}')
REQUIRED_SPACE=16777216  # 16GB in KB

if [ "$AVAILABLE_SPACE" -lt "$REQUIRED_SPACE" ]; then
    echo "Error: Not enough space on NVMe drive"
    echo "Available: $(($AVAILABLE_SPACE / 1024 / 1024))GB"
    echo "Required: 16GB"
    exit 1
fi

# Remove existing swap file if it exists
if [ -f "$SWAP_FILE" ]; then
    echo "Removing existing swap file..."
    swapoff "$SWAP_FILE" 2>/dev/null || true
    rm -f "$SWAP_FILE"
fi

# Create swap file
echo "Creating ${SWAP_SIZE} swap file..."
fallocate -l "$SWAP_SIZE" "$SWAP_FILE"

# Set proper permissions
chmod 600 "$SWAP_FILE"

# Create swap area
echo "Setting up swap area..."
mkswap "$SWAP_FILE"

# Enable swap
echo "Enabling swap..."
swapon "$SWAP_FILE"

# Add to fstab for persistence
echo "Adding swap to /etc/fstab..."
if ! grep -q "$SWAP_FILE" /etc/fstab; then
    echo "$SWAP_FILE none swap sw 0 0" >> /etc/fstab
fi

# Verify swap is active
echo "Verifying swap setup..."
swapon --show

# Set swappiness for better performance
echo "Configuring swap behavior..."
echo "vm.swappiness=10" >> /etc/sysctl.conf
echo "vm.vfs_cache_pressure=50" >> /etc/sysctl.conf

# Apply settings
sysctl -p

echo "Swap setup complete!"
echo "Swap file: $SWAP_FILE"
echo "Size: $SWAP_SIZE"
echo "Status: $(swapon --show | grep "$SWAP_FILE" | awk '{print $4}')"
