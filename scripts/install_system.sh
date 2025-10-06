#!/bin/bash

# BLACK BOX - System installation script
# Complete system setup for NVIDIA Jetson Orin Nano

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
SERVICE_FILE="/etc/systemd/system/blackbox.service"

echo "BLACK BOX - System installation script"
echo "======================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Check if NVMe is mounted
if ! mountpoint -q "/mnt/nvme"; then
    echo "Error: NVMe not mounted at /mnt/nvme"
    echo "Please mount your NVMe drive first:"
    echo "  sudo mount /dev/nvme0n1p1 /mnt/nvme"
    exit 1
fi

# Create blackbox user
echo "Creating blackbox user..."
if ! id "blackbox" &>/dev/null; then
    useradd -r -s /bin/bash -d "$BLACKBOX_DIR" -m blackbox
    usermod -a -G audio,video,plugdev blackbox
    echo "User 'blackbox' created"
else
    echo "User 'blackbox' already exists"
fi

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$BLACKBOX_DIR"/{db,logs,models,data,scripts}
mkdir -p "$BLACKBOX_DIR/models"/{whisper,piper,llm}
mkdir -p "$BLACKBOX_DIR/data"/{sites,backups}

# Copy application files
echo "Copying application files..."
cp -r /path/to/blackbox/* "$BLACKBOX_DIR/"

# Set permissions
chown -R blackbox:blackbox "$BLACKBOX_DIR"
chmod -R 755 "$BLACKBOX_DIR"
chmod +x "$BLACKBOX_DIR/scripts"/*.sh

# Install systemd service
echo "Installing systemd service..."
cp "$BLACKBOX_DIR/blackbox.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable blackbox.service

# Configure Jetson for maximum performance
echo "Configuring Jetson for maximum performance..."

# Set MAXN mode
if command -v nvpmodel &> /dev/null; then
    nvpmodel -m 0
    echo "Set to MAXN mode"
fi

# Set maximum clocks
if command -v jetson_clocks &> /dev/null; then
    jetson_clocks
    echo "Set maximum clocks"
fi

# Configure audio system
echo "Configuring audio system..."

# Create ALSA configuration
cat > /etc/asound.conf << EOF
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOF

# Configure PulseAudio for low latency
cat > /etc/pulse/daemon.conf << EOF
default-sample-rate = 22050
default-sample-format = s16le
default-channels = 2
default-fragments = 2
default-fragment-size-msec = 5
EOF

# Restart audio services
systemctl restart pulseaudio
systemctl restart alsa-state

# Configure display
echo "Configuring display..."

# Set display resolution for 7-inch touchscreen
cat > /etc/X11/xorg.conf.d/99-blackbox.conf << EOF
Section "Monitor"
    Identifier "Touchscreen"
    Modeline "1024x600_60.00" 49.00 1024 1072 1168 1312 600 603 613 624 -hsync +vsync
    Option "PreferredMode" "1024x600_60.00"
EndSection

Section "Screen"
    Identifier "Screen0"
    Monitor "Touchscreen"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1024x600_60.00"
    EndSubSection
EndSection
EOF

# Configure touchscreen
cat > /etc/X11/xorg.conf.d/99-touchscreen.conf << EOF
Section "InputClass"
    Identifier "Touchscreen"
    MatchIsTouchscreen "on"
    Driver "libinput"
    Option "CalibrationMatrix" "1 0 0 0 1 0 0 0 1"
EndSection
EOF

# Configure auto-login
echo "Configuring auto-login..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin blackbox --noclear %I \$TERM
EOF

# Configure X11 auto-start
echo "Configuring X11 auto-start..."
sudo -u blackbox mkdir -p /home/blackbox/.config/autostart
cat > /home/blackbox/.config/autostart/blackbox.desktop << EOF
[Desktop Entry]
Type=Application
Name=BLACK BOX
Comment=AI-assisted password and voice-memo manager
Exec=/usr/bin/python3 $BLACKBOX_DIR/main.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

# Set up log rotation
echo "Setting up log rotation..."
cat > /etc/logrotate.d/blackbox << EOF
$BLACKBOX_DIR/logs/*.log {
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

# Configure power button handling
echo "Configuring power button handling..."
cat > /etc/systemd/system/blackbox-power.service << EOF
[Unit]
Description=BLACK BOX Power Button Handler
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/systemctl poweroff
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable power button service
systemctl enable blackbox-power.service

# Configure network (disable for offline operation)
echo "Configuring network for offline operation..."
systemctl disable NetworkManager
systemctl disable networking
systemctl stop NetworkManager
systemctl stop networking

# Set up firewall to block all network access
ufw --force reset
ufw default deny incoming
ufw default deny outgoing
ufw --force enable

# Configure system for headless operation
echo "Configuring system for headless operation..."
systemctl set-default multi-user.target

# Disable unnecessary services
systemctl disable bluetooth
systemctl disable cups
systemctl disable avahi-daemon
systemctl disable ModemManager

# Configure memory management
echo "Configuring memory management..."
cat >> /etc/sysctl.conf << EOF
# BLACK BOX memory optimizations
vm.swappiness=10
vm.vfs_cache_pressure=50
vm.dirty_ratio=15
vm.dirty_background_ratio=5
kernel.panic=10
EOF

# Apply sysctl settings
sysctl -p

# Create startup script
echo "Creating startup script..."
cat > "$BLACKBOX_DIR/startup.sh" << 'EOF'
#!/bin/bash

# BLACK BOX startup script
echo "Starting BLACK BOX..."

# Wait for NVMe to be ready
while [ ! -d "/mnt/nvme/blackbox" ]; do
    echo "Waiting for NVMe mount..."
    sleep 2
done

# Start X server
export DISPLAY=:0
startx -- -nocursor &

# Wait for X server to start
sleep 5

# Start BLACK BOX application
cd /mnt/nvme/blackbox
python3 main.py
EOF

chmod +x "$BLACKBOX_DIR/startup.sh"

# Add startup script to .bashrc
echo "Adding startup script to .bashrc..."
cat >> /home/blackbox/.bashrc << EOF

# BLACK BOX startup
if [ -z "\$DISPLAY" ] && [ "\$(tty)" = "/dev/tty1" ]; then
    exec /mnt/nvme/blackbox/startup.sh
fi
EOF

# Create backup script
echo "Creating backup script..."
cat > "$BLACKBOX_DIR/scripts/backup.sh" << 'EOF'
#!/bin/bash

# BLACK BOX backup script
BACKUP_DIR="/mnt/nvme/blackbox/data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/blackbox_backup_$DATE.db"

mkdir -p "$BACKUP_DIR"

# Create database backup
if [ -f "/mnt/nvme/blackbox/db/vault.db" ]; then
    cp "/mnt/nvme/blackbox/db/vault.db" "$BACKUP_FILE"
    echo "Backup created: $BACKUP_FILE"
else
    echo "No database found to backup"
fi

# Keep only last 7 backups
cd "$BACKUP_DIR"
ls -t blackbox_backup_*.db | tail -n +8 | xargs -r rm

echo "Backup complete"
EOF

chmod +x "$BLACKBOX_DIR/scripts/backup.sh"

# Set up daily backup cron job
echo "Setting up daily backup..."
(crontab -u blackbox -l 2>/dev/null; echo "0 2 * * * /mnt/nvme/blackbox/scripts/backup.sh") | crontab -u blackbox -

# Final permissions
chown -R blackbox:blackbox "$BLACKBOX_DIR"
chmod -R 755 "$BLACKBOX_DIR"

echo ""
echo "BLACK BOX system installation complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Run: sudo ./scripts/setup_swap.sh"
echo "2. Run: sudo ./scripts/install_models.sh"
echo "3. Reboot the system"
echo ""
echo "The system will automatically start BLACK BOX on boot."
echo "Access the system via the 7-inch touchscreen."
echo ""
echo "For troubleshooting, check logs at: $BLACKBOX_DIR/logs/"
echo "For backups, check: $BLACKBOX_DIR/data/backups/"
