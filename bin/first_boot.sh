#!/bin/bash

# BLACK BOX - First boot provisioning script
# Creates folders, sets permissions, downloads/copies models, writes config

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
LOG_FILE="$BLACKBOX_DIR/logs/first_boot.log"

echo "BLACK BOX - First Boot Provisioning"
echo "==================================="

# Create log file
mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Starting first boot provisioning at $(date)"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Check if NVMe is mounted
if ! mountpoint -q "/mnt/nvme"; then
    echo "Error: NVMe not mounted at /mnt/nvme"
    echo "Please mount your NVMe drive first:"
    echo "  sudo mount /dev/nvme0n1p1 /mnt/nvme"
    exit 1
fi

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$BLACKBOX_DIR"/{db,logs,models,media,config,assets,catalog,backups}
mkdir -p "$BLACKBOX_DIR/models"/{whisper,piper,llm}
mkdir -p "$BLACKBOX_DIR/assets"/{beeps,images,sounds}
mkdir -p "$BLACKBOX_DIR/config"
mkdir -p "$BLACKBOX_DIR/catalog"
mkdir -p "$BLACKBOX_DIR/db/backups"

# Set permissions
echo "Setting permissions..."
chown -R blackbox:blackbox "$BLACKBOX_DIR"
chmod -R 755 "$BLACKBOX_DIR"
chmod -R 700 "$BLACKBOX_DIR/db"  # Secure database directory

# Create default configuration files
echo "Creating default configuration files..."

# Audio configuration
cat > "$BLACKBOX_DIR/config/audio.json" << 'EOF'
{
  "input": [],
  "output": [],
  "default_input": null,
  "default_output": null,
  "sample_rate": 16000,
  "channels": 1
}
EOF

# Voice configuration
cat > "$BLACKBOX_DIR/config/voice.json" << 'EOF'
{
  "voice": "en_US-lessac-medium",
  "speed": 1.0,
  "volume": 0.8,
  "pitch": 1.0
}
EOF

# Application configuration
cat > "$BLACKBOX_DIR/config/app.yaml" << 'EOF'
# BLACK BOX Application Configuration
system:
  base_dir: "/mnt/nvme/blackbox"
  auto_lock:
    enabled: true
    timeout_seconds: 300
  logging:
    level: "INFO"
    max_log_size_mb: 100
    backup_count: 4

audio:
  microphone:
    sample_rate: 16000
    channels: 1
  speaker:
    sample_rate: 22050
    channels: 2
  vad:
    window_ms: 700
    threshold: 0.5

asr:
  whisper:
    model_path: "/mnt/nvme/blackbox/models/whisper/whisper-tiny.en.bin"
    temperature: 0.0
    temperature_fallback: 0.2
    n_best: 3
    gpu_acceleration: true

nlp:
  heuristics:
    fuzzy_threshold: 0.88
    llm_threshold: 0.82
    confirmation_threshold: 0.75
  llm:
    enabled: false
    model_path: "/mnt/nvme/blackbox/models/llm/"
    max_new_tokens: 16
    temperature: 0.0

ui:
  display:
    resolution: "1024x600"
    fullscreen: true
    high_contrast: true
  colors:
    background: "#000000"
    text: "#FFFFFF"
    accent: "#FFFF00"
  typography:
    font_family: "Arial"
    font_size_large: 48
    font_size_medium: 24

security:
  encryption:
    algorithm: "AES-256"
    kdf: "Argon2id"
    kdf_params:
      time_cost: 3
      memory_cost: 65536
      parallelism: 4
EOF

# Create default site catalog
cat > "$BLACKBOX_DIR/catalog/sites.json" << 'EOF'
{
  "sites": {
    "gmail": ["gmail", "google mail", "googlemail"],
    "google": ["google", "googol"],
    "facebook": ["facebook", "fb", "face book"],
    "amazon": ["amazon", "amazon.com"],
    "netflix": ["netflix", "net flix"],
    "youtube": ["youtube", "you tube", "yt"],
    "twitter": ["twitter", "x", "tweet"],
    "instagram": ["instagram", "insta", "ig"],
    "linkedin": ["linkedin", "linked in"],
    "paypal": ["paypal", "pay pal"],
    "ebay": ["ebay", "e bay"],
    "spotify": ["spotify", "spot ify"],
    "apple": ["apple", "apple.com", "icloud"],
    "microsoft": ["microsoft", "ms", "outlook", "hotmail"],
    "bank": ["bank", "banking", "chase", "wells fargo", "bank of america"]
  }
}
EOF

# Create .env file
cat > "$BLACKBOX_DIR/.env" << 'EOF'
# BLACK BOX Environment Variables
BLACKBOX_BASE_DIR=/mnt/nvme/blackbox
BLACKBOX_LOG_LEVEL=INFO
BLACKBOX_AUTO_LOCK_TIMEOUT=300
BLACKBOX_GPU_ACCELERATION=true
BLACKBOX_OFFLINE_MODE=true
EOF

# Download/copy models if not present
echo "Checking for AI models..."

# Check Whisper model
if [ ! -f "$BLACKBOX_DIR/models/whisper/whisper-tiny.en.bin" ]; then
    echo "Whisper model not found, will need to be installed"
    echo "Run: sudo ./scripts/install_models.sh"
else
    echo "Whisper model found"
fi

# Check Piper model
if [ ! -f "$BLACKBOX_DIR/models/piper/en_US-lessac-medium.onnx" ]; then
    echo "Piper model not found, will need to be installed"
    echo "Run: sudo ./scripts/install_models.sh"
else
    echo "Piper model found"
fi

# Create swap file if missing
echo "Checking swap configuration..."
if ! swapon --show | grep -q "/mnt/nvme/swapfile"; then
    echo "Swap file not configured, will need to be created"
    echo "Run: sudo ./scripts/setup_swap.sh"
else
    echo "Swap file configured"
fi

# Generate beep files
echo "Generating beep files..."
if [ -f "$BLACKBOX_DIR/assets/beeps/generate_beeps.py" ]; then
    cd "$BLACKBOX_DIR/assets/beeps"
    python3 generate_beeps.py
    echo "Beep files generated"
else
    echo "Beep generator not found, creating simple beep files..."
    # Create simple beep files using sox if available
    if command -v sox >/dev/null 2>&1; then
        sox -n "$BLACKBOX_DIR/assets/beeps/recording_start.wav" synth 0.3 sine 800
        sox -n "$BLACKBOX_DIR/assets/beeps/recording_stop.wav" synth 0.2 sine 600
        sox -n "$BLACKBOX_DIR/assets/beeps/success.wav" synth 0.15 sine 1000
        sox -n "$BLACKBOX_DIR/assets/beeps/error.wav" synth 0.5 sine 400
        sox -n "$BLACKBOX_DIR/assets/beeps/confirm.wav" synth 0.2 sine 700
        echo "Simple beep files created"
    else
        echo "Warning: sox not available, beep files not created"
    fi
fi

# Set up log rotation
echo "Setting up log rotation..."
cat > /etc/logrotate.d/blackbox << 'EOF'
/mnt/nvme/blackbox/logs/*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 644 blackbox blackbox
    postrotate
        systemctl reload blackbox.service
    endscript
}
EOF

# Create systemd service file
echo "Creating systemd service..."
cat > /etc/systemd/system/blackbox.service << 'EOF'
[Unit]
Description=BLACK BOX - AI-assisted password and voice-memo manager
Documentation=https://github.com/blackbox/blackbox
After=multi-user.target sound.target
Wants=multi-user.target

[Service]
Type=simple
User=blackbox
Group=blackbox
WorkingDirectory=/mnt/nvme/blackbox
ExecStart=/usr/bin/python3 /mnt/nvme/blackbox/main.py
ExecStop=/bin/kill -TERM $MAINPID
Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal
SyslogIdentifier=blackbox

# Environment variables
Environment=PYTHONPATH=/mnt/nvme/blackbox
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/blackbox/.Xauthority

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/mnt/nvme/blackbox
ReadWritePaths=/tmp

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

# GPU access for Jetson
SupplementaryGroups=video
SupplementaryGroups=audio

[Install]
WantedBy=multi-user.target
EOF

# Enable service
systemctl daemon-reload
systemctl enable blackbox.service

# Set up audio device probing
echo "Setting up audio device probing..."
if [ -f "$BLACKBOX_DIR/blackbox/audio/probe.py" ]; then
    cd "$BLACKBOX_DIR"
    python3 -c "
from blackbox.audio.probe import AudioDeviceProbe
probe = AudioDeviceProbe()
devices = probe.probe_devices()
print('Audio devices probed and configured')
"
else
    echo "Warning: Audio probe script not found"
fi

# Create first boot completion marker
echo "Creating first boot completion marker..."
touch "$BLACKBOX_DIR/.first_boot_complete"
echo "$(date)" > "$BLACKBOX_DIR/.first_boot_complete"

# Set final permissions
echo "Setting final permissions..."
chown -R blackbox:blackbox "$BLACKBOX_DIR"
chmod -R 755 "$BLACKBOX_DIR"
chmod -R 700 "$BLACKBOX_DIR/db"

echo ""
echo "First boot provisioning completed successfully!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Install AI models: sudo ./scripts/install_models.sh"
echo "2. Set up swap file: sudo ./scripts/setup_swap.sh"
echo "3. Test system: sudo ./scripts/test_system.sh"
echo "4. Reboot system: sudo reboot"
echo ""
echo "The system will automatically start BLACK BOX on boot."
echo "Log file: $LOG_FILE"

# Create summary report
cat > "$BLACKBOX_DIR/first_boot_report.txt" << EOF
BLACK BOX First Boot Report
==========================
Date: $(date)
User: $(whoami)
Hostname: $(hostname)

Directory Structure:
$(find "$BLACKBOX_DIR" -type d | sort)

Configuration Files:
$(find "$BLACKBOX_DIR/config" -name "*.json" -o -name "*.yaml" -o -name "*.env" | sort)

Models Status:
- Whisper: $([ -f "$BLACKBOX_DIR/models/whisper/whisper-tiny.en.bin" ] && echo "Present" || echo "Missing")
- Piper: $([ -f "$BLACKBOX_DIR/models/piper/en_US-lessac-medium.onnx" ] && echo "Present" || echo "Missing")

Swap Status:
$(swapon --show | grep -q "/mnt/nvme/swapfile" && echo "Configured" || echo "Not configured")

Service Status:
$(systemctl is-enabled blackbox.service)

Next Steps:
1. Install AI models: sudo ./scripts/install_models.sh
2. Set up swap file: sudo ./scripts/setup_swap.sh
3. Test system: sudo ./scripts/test_system.sh
4. Reboot system: sudo reboot
EOF

echo "First boot report saved to: $BLACKBOX_DIR/first_boot_report.txt"
