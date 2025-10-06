# BLACK BOX

AI-assisted password and voice-memo manager for elderly users

## Overview

BLACK BOX is a complete offline software stack designed for elderly users to manage passwords and voice memos using natural speech interaction. The system runs on an NVIDIA Jetson Orin Nano 8GB with a 7-inch touchscreen, USB microphone, and USB speaker.

## Features

- **Voice Recognition**: GPU-optimized Whisper.cpp with VAD for elderly speech patterns
- **Text-to-Speech**: Piper TTS with pre-loaded models for instant feedback
- **Intent Resolution**: Heuristic + LLM fallback for site name recognition
- **Encrypted Storage**: SQLCipher database with Argon2id KDF
- **Touch Interface**: Fullscreen PySide6 UI with large buttons and high contrast
- **Offline Operation**: Complete system runs without internet after setup
- **Auto-start**: Boots headless and starts application automatically

## Hardware Requirements

- NVIDIA Jetson Orin Nano 8GB
- 7-inch HDMI/USB touchscreen (1024×600)
- USB microphone
- USB speaker
- Powered USB hub
- SK Hynix NVMe SSD (mounted at /mnt/nvme)

## Installation

### Prerequisites

- NVIDIA Jetson Orin Nano 8GB with JetPack 6
- Ubuntu 22.04 LTS (via JetPack 6)
- 7-inch HDMI/USB touchscreen (1024×600)
- USB microphone and speaker
- Powered USB hub
- SK Hynix NVMe SSD (minimum 32GB)

### 1. JetPack 6 Setup

1. Download JetPack 6 from NVIDIA Developer website
2. Flash Ubuntu 22.04 to microSD card
3. Boot Jetson from microSD card
4. Complete initial Ubuntu setup
5. Update system: `sudo apt update && sudo apt upgrade -y`

### 2. NVMe Drive Setup

```bash
# Find NVMe device
lsblk

# Create partition (if needed)
sudo parted /dev/nvme0n1 mklabel gpt
sudo parted /dev/nvme0n1 mkpart primary ext4 0% 100%

# Format partition
sudo mkfs.ext4 /dev/nvme0n1p1

# Create mount point and mount
sudo mkdir -p /mnt/nvme
sudo mount /dev/nvme0n1p1 /mnt/nvme

# Add to fstab for persistence
echo "/dev/nvme0n1p1 /mnt/nvme ext4 defaults 0 2" | sudo tee -a /etc/fstab
```

### 3. First Boot Provisioning

```bash
# Copy BLACK BOX files to NVMe
sudo cp -r /path/to/BLACKBOXVERSIONONE /mnt/nvme/blackbox
cd /mnt/nvme/blackbox

# Run first boot provisioning
sudo ./bin/first_boot.sh
```

### 4. System Installation

```bash
# Run system installation
sudo ./scripts/install_system.sh
```

### 5. Swap Configuration

```bash
# Create 16GB swap file
sudo ./scripts/setup_swap.sh
```

### 6. Model Installation

```bash
# Install AI models (Whisper, Piper, LLM)
sudo ./scripts/install_models.sh
```

### 7. System Testing

```bash
# Run comprehensive system tests
sudo ./scripts/test_system.sh

# Run individual component tests
sudo ./scripts/test_audio.sh
sudo ./scripts/test_asr.sh
sudo ./scripts/test_vault.py
sudo ./scripts/test_ui.py
```

### 8. Reboot

```bash
sudo reboot
```

## Usage

1. **First Boot**: Enter master passphrase using virtual keyboard
2. **Save Password**: Say "Save password for [site] [password]"
3. **Retrieve Password**: Say "Get password for [site]"
4. **Reveal Password**: Touch "REVEAL" button (10-second countdown)

## Performance Targets

- ASR: ≤ 1.5 seconds
- Heuristic resolve: ≤ 0.2 seconds
- LLM resolve: ≤ 1 second
- TTS prompt: ≤ 0.4 seconds
- End-to-end interaction: < 4 seconds

## Architecture

```
blackbox/
├── audio/
│   ├── asr.py          # Whisper.cpp ASR with VAD
│   └── tts.py          # Piper TTS with audio routing
├── nlp/
│   └── resolve.py      # Intent handling + entity resolution
├── vault/
│   └── db.py           # SQLCipher encrypted database
├── ui/
│   └── main.py         # PySide6 fullscreen interface
└── main.py             # Application entry point
```

## Configuration

### Audio Settings
- Microphone: 16 kHz mono
- Speaker: 22.05 kHz stereo
- VAD window: 700 ms
- TTS sample rate: 22.05 kHz

### Security
- AES-256 encryption
- Argon2id KDF
- Auto-lock after 5 minutes idle
- Master passphrase stored in RAM only

### Display
- Resolution: 1024×600
- Fullscreen mode
- High contrast (black background, yellow/white text)
- Touch buttons: ≥ 150×150 px
- Font size: ≥ 36 pt

## Troubleshooting

### Common Issues

#### No Sound
```bash
# Check audio devices
aplay -l
arecord -l

# Test audio output
speaker-test -c 2 -t sine -f 1000 -l 1

# Check ALSA configuration
cat /etc/asound.conf

# Restart audio services
sudo systemctl restart pulseaudio
sudo systemctl restart alsa-state
```

#### Microphone Not Listed
```bash
# Check USB devices
lsusb

# Check audio devices
arecord -l

# Test microphone
arecord -f S16_LE -r 16000 -c 1 -d 3 /tmp/test.wav
aplay /tmp/test.wav

# Check permissions
groups
# User should be in 'audio' group
```

#### Display Issues (eglfs not showing fullscreen)
```bash
# Check display resolution
xrandr

# Check X11 configuration
cat /etc/X11/xorg.conf.d/99-blackbox.conf

# Reconfigure display
sudo dpkg-reconfigure xserver-xorg

# Restart X server
sudo systemctl restart gdm
```

#### Service Not Starting
```bash
# Check service status
systemctl status blackbox

# Check service logs
journalctl -u blackbox -f

# Check application logs
tail -f /mnt/nvme/blackbox/logs/app.log

# Check systemd service file
cat /etc/systemd/system/blackbox.service
```

#### Performance Issues
```bash
# Check GPU status
nvidia-smi

# Check memory usage
free -h

# Check swap usage
swapon --show

# Check CPU usage
htop

# Restart with MAXN mode
sudo nvpmodel -m 0
sudo jetson_clocks
```

#### Model Loading Issues
```bash
# Check model files
ls -la /mnt/nvme/blackbox/models/whisper/
ls -la /mnt/nvme/blackbox/models/piper/

# Test Whisper
/mnt/nvme/blackbox/models/whisper/whisper --help

# Test Piper
/mnt/nvme/blackbox/models/piper/piper --help
```

#### Network Issues (Offline Mode)
```bash
# Check network interfaces
ip link show

# Disable network (for offline operation)
sudo systemctl stop NetworkManager
sudo systemctl stop networking

# Check firewall
sudo ufw status
```

### System Diagnostics

#### Run Health Check
```bash
# Run comprehensive health check
cd /mnt/nvme/blackbox
python3 -c "
from blackbox.health.health_check import initialize_health_checks, get_health_status
initialize_health_checks()
status = get_health_status()
print('Health Status:', status['overall_status'])
for name, check in status['checks'].items():
    print(f'{name}: {check[\"status\"]} - {check[\"message\"]}')
"
```

#### Check System Resources
```bash
# Check disk usage
df -h /mnt/nvme

# Check directory sizes
du -sh /mnt/nvme/blackbox/*

# Check log file sizes
ls -lh /mnt/nvme/blackbox/logs/

# Check swap usage
swapon --show
```

#### Performance Monitoring
```bash
# Monitor system resources
htop

# Monitor GPU usage
watch -n 1 nvidia-smi

# Monitor disk I/O
iostat -x 1

# Monitor network (should be disabled)
iftop
```

### Reset and Recovery

#### Soft Reset
```bash
# Stop service
sudo systemctl stop blackbox

# Clear logs
sudo rm -f /mnt/nvme/blackbox/logs/*.log

# Restart service
sudo systemctl start blackbox
```

#### Hard Reset
```bash
# Stop service
sudo systemctl stop blackbox

# Clear all logs and temporary files
sudo rm -rf /mnt/nvme/blackbox/logs/*
sudo rm -rf /tmp/blackbox_*

# Restart service
sudo systemctl start blackbox
```

#### Factory Reset
```bash
# Stop service
sudo systemctl stop blackbox

# Remove database (WARNING: This will delete all passwords)
sudo rm -f /mnt/nvme/blackbox/db/vault.db

# Clear all data
sudo rm -rf /mnt/nvme/blackbox/db/*
sudo rm -rf /mnt/nvme/blackbox/logs/*
sudo rm -rf /mnt/nvme/blackbox/media/*

# Restart service (will prompt for new master passphrase)
sudo systemctl start blackbox
```

### Log Analysis

#### Application Logs
```bash
# Main application log
tail -f /mnt/nvme/blackbox/logs/app.log

# ASR log
tail -f /mnt/nvme/blackbox/logs/asr.log

# Vault log (no secrets)
tail -f /mnt/nvme/blackbox/logs/vault.log

# TTS log
tail -f /mnt/nvme/blackbox/logs/tts.log

# UI log
tail -f /mnt/nvme/blackbox/logs/ui.log
```

#### System Logs
```bash
# Systemd service logs
journalctl -u blackbox -f

# System logs
journalctl -f

# Audio logs
journalctl -u pulseaudio -f
```

### Support and Recovery

#### Backup and Restore
```bash
# Create backup
sudo /mnt/nvme/blackbox/scripts/backup.sh

# List backups
ls -la /mnt/nvme/blackbox/data/backups/

# Restore from backup (if needed)
sudo cp /mnt/nvme/blackbox/data/backups/blackbox_backup_YYYYMMDD_HHMMSS.db /mnt/nvme/blackbox/db/vault.db
```

#### Emergency Access
```bash
# If UI is not responding, access via SSH
ssh blackbox@<jetson-ip>

# Or access via console
# Connect keyboard and monitor to Jetson
# Login as blackbox user
# Check service status
systemctl status blackbox
```

## Security Notes

- System runs entirely offline after setup
- All data encrypted with user's master passphrase
- No network access enabled
- Auto-lock on inactivity
- Secure deletion of sensitive data from memory

## Support

For technical support or issues, check the logs at `/mnt/nvme/blackbox/logs/blackbox.log`.

## License

Proprietary - BLACK BOX Team
