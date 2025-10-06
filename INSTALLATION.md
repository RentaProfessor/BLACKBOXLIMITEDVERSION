# BLACK BOX Installation Guide

Complete installation guide for the BLACK BOX AI-assisted password and voice-memo manager on NVIDIA Jetson Orin Nano 8GB.

## Prerequisites

### Hardware Requirements
- NVIDIA Jetson Orin Nano 8GB
- 7-inch HDMI/USB touchscreen (1024×600)
- USB microphone
- USB speaker
- Powered USB hub
- SK Hynix NVMe SSD (minimum 32GB)
- MicroSD card (for Jetpack 6 installation)

### Software Requirements
- Ubuntu 22.04 LTS (via Jetpack 6)
- Internet connection (for initial setup only)

## Step 1: Initial System Setup

### 1.1 Install Jetpack 6
1. Download Jetpack 6 from NVIDIA Developer website
2. Flash Ubuntu 22.04 to microSD card
3. Boot Jetson from microSD card
4. Complete initial Ubuntu setup

### 1.2 Mount NVMe Drive
```bash
# Find NVMe device
lsblk

# Create partition (if needed)
sudo parted /dev/nvme0n1 mklabel gpt
sudo parted /dev/nvme0n1 mkpart primary ext4 0% 100%

# Format partition
sudo mkfs.ext4 /dev/nvme0n1p1

# Create mount point
sudo mkdir -p /mnt/nvme

# Mount NVMe drive
sudo mount /dev/nvme0n1p1 /mnt/nvme

# Add to fstab for persistence
echo "/dev/nvme0n1p1 /mnt/nvme ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

### 1.3 Update System
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git wget curl
```

## Step 2: Install BLACK BOX

### 2.1 Download BLACK BOX
```bash
# Clone or copy BLACK BOX files to NVMe
sudo cp -r /path/to/BLACKBOXVERSIONONE /mnt/nvme/blackbox
cd /mnt/nvme/blackbox
```

### 2.2 Run System Installation
```bash
# Make scripts executable
sudo chmod +x scripts/*.sh

# Run system installation
sudo ./scripts/install_system.sh
```

This script will:
- Create blackbox user
- Set up directory structure
- Install systemd service
- Configure Jetson for maximum performance
- Set up audio system
- Configure display for 7-inch touchscreen
- Set up auto-login and X11 auto-start
- Configure security settings

### 2.3 Set Up Swap File
```bash
# Create 16GB swap file
sudo ./scripts/setup_swap.sh
```

### 2.4 Install AI Models
```bash
# Install Whisper.cpp, Piper TTS, and dependencies
sudo ./scripts/install_models.sh
```

This script will:
- Install system dependencies
- Build and install Whisper.cpp with GPU support
- Install Piper TTS
- Download AI models
- Install Python dependencies
- Set up TensorRT-LLM (if available)

## Step 3: Configuration

### 3.1 Audio Configuration
```bash
# Test audio devices
aplay -l
arecord -l

# Configure audio devices if needed
sudo nano /etc/asound.conf
```

### 3.2 Display Configuration
```bash
# Test display resolution
xrandr

# Calibrate touchscreen if needed
sudo apt install xinput-calibrator
xinput_calibrator
```

### 3.3 Network Configuration (Offline Mode)
```bash
# Disable network interfaces
sudo systemctl disable NetworkManager
sudo systemctl disable networking
sudo systemctl stop NetworkManager
sudo systemctl stop networking

# Configure firewall
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default deny outgoing
sudo ufw --force enable
```

## Step 4: Testing

### 4.1 Run System Tests
```bash
# Run comprehensive system tests
sudo ./scripts/test_system.sh
```

### 4.2 Manual Testing
```bash
# Test Whisper.cpp
./models/whisper/whisper --help

# Test Piper TTS
echo "Hello" | ./models/piper/piper --model ./models/piper/en_US-lessac-medium.onnx --output_file test.wav
aplay test.wav

# Test Python application
python3 main.py
```

## Step 5: Final Setup

### 5.1 Reboot System
```bash
sudo reboot
```

### 5.2 First Boot Setup
1. System will boot to touchscreen
2. BLACK BOX will start automatically
3. Enter master passphrase using virtual keyboard
4. Test voice commands:
   - "Save password for gmail mypassword123"
   - "Get password for gmail"

### 5.3 Verify Installation
- Check that all services are running
- Test voice recognition
- Test password storage/retrieval
- Verify offline operation

## Troubleshooting

### Common Issues

#### Audio Not Working
```bash
# Check audio devices
aplay -l
arecord -l

# Restart audio services
sudo systemctl restart pulseaudio
sudo systemctl restart alsa-state

# Test audio
speaker-test -c 2
```

#### Display Issues
```bash
# Check display resolution
xrandr

# Reconfigure display
sudo dpkg-reconfigure xserver-xorg

# Restart X server
sudo systemctl restart gdm
```

#### Performance Issues
```bash
# Check GPU status
nvidia-smi

# Check memory usage
free -h

# Check swap usage
swapon --show

# Restart with MAXN mode
sudo nvpmodel -m 0
sudo jetson_clocks
```

#### Service Issues
```bash
# Check service status
systemctl status blackbox

# Check logs
journalctl -u blackbox -f

# Restart service
sudo systemctl restart blackbox
```

### Log Files
- Application logs: `/mnt/nvme/blackbox/logs/blackbox.log`
- System logs: `journalctl -u blackbox`
- Test results: `/mnt/nvme/blackbox/logs/test_results.log`

### Performance Monitoring
```bash
# Monitor system resources
htop

# Monitor GPU usage
watch -n 1 nvidia-smi

# Monitor disk usage
df -h /mnt/nvme
```

## Security Considerations

### Offline Operation
- System runs entirely offline after setup
- No network interfaces enabled
- Firewall blocks all network access
- No internet connectivity required

### Data Protection
- All data encrypted with user's master passphrase
- Argon2id key derivation function
- AES-256 encryption
- Auto-lock after 5 minutes of inactivity
- Secure memory management

### Physical Security
- System boots directly to BLACK BOX
- No shell access without physical intervention
- Touchscreen-only interface
- No external ports accessible during operation

## Maintenance

### Regular Backups
- Automatic daily backups to `/mnt/nvme/blackbox/data/backups/`
- Manual backup: `./scripts/backup.sh`
- Backup retention: 30 days

### Log Rotation
- Logs rotate weekly
- Maximum log size: 100MB
- Backup count: 5 files

### System Updates
- No automatic updates (offline system)
- Manual updates require internet connection
- Update process:
  1. Enable network temporarily
  2. Run updates
  3. Disable network
  4. Reboot

## Support

### Getting Help
1. Check log files for error messages
2. Run system tests: `./scripts/test_system.sh`
3. Check service status: `systemctl status blackbox`
4. Review this installation guide

### System Recovery
If the system becomes unresponsive:
1. Power cycle the device
2. Boot from microSD card
3. Mount NVMe drive
4. Check and repair filesystem
5. Restore from backup if needed

## Performance Targets

The system is designed to meet these performance targets:
- ASR: ≤ 1.5 seconds
- Heuristic resolve: ≤ 0.2 seconds
- LLM resolve: ≤ 1 second
- TTS prompt: ≤ 0.4 seconds
- End-to-end interaction: < 4 seconds

If performance targets are not met, check:
- GPU acceleration is enabled
- Swap file is properly configured
- System is in MAXN mode
- No background processes consuming resources
