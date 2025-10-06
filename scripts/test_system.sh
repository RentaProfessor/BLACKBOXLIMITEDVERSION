#!/bin/bash

# BLACK BOX - System test script
# Tests all components and performance targets

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
TEST_RESULTS="$BLACKBOX_DIR/logs/test_results.log"

echo "BLACK BOX - System Test Suite"
echo "============================="

# Create test results file
mkdir -p "$(dirname "$TEST_RESULTS")"
echo "BLACK BOX Test Results - $(date)" > "$TEST_RESULTS"
echo "=================================" >> "$TEST_RESULTS"

# Test functions
test_passed() {
    echo "✓ $1" | tee -a "$TEST_RESULTS"
}

test_failed() {
    echo "✗ $1" | tee -a "$TEST_RESULTS"
}

test_warning() {
    echo "⚠ $1" | tee -a "$TEST_RESULTS"
}

# Test 1: System Requirements
echo ""
echo "1. Testing System Requirements..."

# Check NVMe mount
if mountpoint -q "/mnt/nvme"; then
    test_passed "NVMe drive mounted"
else
    test_failed "NVMe drive not mounted"
fi

# Check available space
AVAILABLE_SPACE=$(df /mnt/nvme | awk 'NR==2 {print $4}')
if [ "$AVAILABLE_SPACE" -gt 10485760 ]; then  # 10GB
    test_passed "Sufficient disk space available"
else
    test_failed "Insufficient disk space"
fi

# Check memory
TOTAL_MEMORY=$(free -m | awk 'NR==2{print $2}')
if [ "$TOTAL_MEMORY" -ge 8000 ]; then
    test_passed "Sufficient memory (${TOTAL_MEMORY}MB)"
else
    test_failed "Insufficient memory (${TOTAL_MEMORY}MB)"
fi

# Check swap
SWAP_SIZE=$(swapon --show | awk 'NR==2{print $3}' | sed 's/[^0-9]//g')
if [ -n "$SWAP_SIZE" ] && [ "$SWAP_SIZE" -ge 16000000 ]; then  # 16GB
    test_passed "Swap file configured (${SWAP_SIZE}KB)"
else
    test_warning "Swap file not configured or too small"
fi

# Test 2: Audio System
echo ""
echo "2. Testing Audio System..."

# Check audio devices
if aplay -l | grep -q "card"; then
    test_passed "Audio output devices detected"
else
    test_failed "No audio output devices found"
fi

if arecord -l | grep -q "card"; then
    test_passed "Audio input devices detected"
else
    test_failed "No audio input devices found"
fi

# Test audio playback
if timeout 2 aplay /usr/share/sounds/alsa/Front_Left.wav 2>/dev/null; then
    test_passed "Audio playback working"
else
    test_warning "Audio playback test failed"
fi

# Test 3: AI Models
echo ""
echo "3. Testing AI Models..."

# Check Whisper.cpp
if [ -f "$BLACKBOX_DIR/models/whisper/whisper" ]; then
    test_passed "Whisper.cpp installed"
else
    test_failed "Whisper.cpp not found"
fi

if [ -f "$BLACKBOX_DIR/models/whisper/whisper-tiny.en.bin" ]; then
    test_passed "Whisper model available"
else
    test_failed "Whisper model not found"
fi

# Check Piper TTS
if [ -f "$BLACKBOX_DIR/models/piper/piper" ]; then
    test_passed "Piper TTS installed"
else
    test_failed "Piper TTS not found"
fi

if [ -f "$BLACKBOX_DIR/models/piper/en_US-lessac-medium.onnx" ]; then
    test_passed "Piper TTS model available"
else
    test_failed "Piper TTS model not found"
fi

# Test 4: Python Dependencies
echo ""
echo "4. Testing Python Dependencies..."

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    test_passed "Python version compatible ($PYTHON_VERSION)"
else
    test_failed "Python version incompatible ($PYTHON_VERSION)"
fi

# Check required packages
REQUIRED_PACKAGES=(
    "PySide6"
    "pysqlcipher3"
    "argon2"
    "rapidfuzz"
    "metaphone"
    "sounddevice"
    "numpy"
    "scipy"
)

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        test_passed "Package $package available"
    else
        test_failed "Package $package not available"
    fi
done

# Test 5: Database
echo ""
echo "5. Testing Database..."

# Check SQLCipher
if python3 -c "import sqlite3; print(sqlite3.sqlite_version)" | grep -q "3."; then
    test_passed "SQLite available"
else
    test_failed "SQLite not available"
fi

# Check database directory
if [ -d "$BLACKBOX_DIR/db" ]; then
    test_passed "Database directory exists"
else
    test_failed "Database directory not found"
fi

# Test 6: System Service
echo ""
echo "6. Testing System Service..."

# Check service file
if [ -f "/etc/systemd/system/blackbox.service" ]; then
    test_passed "Systemd service file installed"
else
    test_failed "Systemd service file not found"
fi

# Check service status
if systemctl is-enabled blackbox.service >/dev/null 2>&1; then
    test_passed "BLACK BOX service enabled"
else
    test_warning "BLACK BOX service not enabled"
fi

# Test 7: Performance Tests
echo ""
echo "7. Running Performance Tests..."

# Test ASR performance
echo "Testing ASR performance..."
ASR_START=$(date +%s%N)
if [ -f "$BLACKBOX_DIR/models/whisper/whisper" ]; then
    # Create a test audio file (1 second of silence)
    timeout 1 arecord -f S16_LE -r 16000 -c 1 /tmp/test_audio.wav 2>/dev/null || true
    if [ -f "/tmp/test_audio.wav" ]; then
        timeout 5 "$BLACKBOX_DIR/models/whisper/whisper" -m "$BLACKBOX_DIR/models/whisper/whisper-tiny.en.bin" -f /tmp/test_audio.wav --no-timestamps --print-colors false >/dev/null 2>&1
        ASR_END=$(date +%s%N)
        ASR_TIME=$(( (ASR_END - ASR_START) / 1000000 ))  # Convert to milliseconds
        
        if [ "$ASR_TIME" -lt 1500 ]; then
            test_passed "ASR performance target met (${ASR_TIME}ms < 1500ms)"
        else
            test_warning "ASR performance target not met (${ASR_TIME}ms > 1500ms)"
        fi
        
        rm -f /tmp/test_audio.wav
    else
        test_warning "Could not create test audio file"
    fi
else
    test_failed "Cannot test ASR - Whisper not available"
fi

# Test TTS performance
echo "Testing TTS performance..."
TTS_START=$(date +%s%N)
if [ -f "$BLACKBOX_DIR/models/piper/piper" ]; then
    echo "Hello" | timeout 5 "$BLACKBOX_DIR/models/piper/piper" --model "$BLACKBOX_DIR/models/piper/en_US-lessac-medium.onnx" --output_file /tmp/test_tts.wav >/dev/null 2>&1
    TTS_END=$(date +%s%N)
    TTS_TIME=$(( (TTS_END - TTS_START) / 1000000 ))  # Convert to milliseconds
    
    if [ "$TTS_TIME" -lt 400 ]; then
        test_passed "TTS performance target met (${TTS_TIME}ms < 400ms)"
    else
        test_warning "TTS performance target not met (${TTS_TIME}ms > 400ms)"
    fi
    
    rm -f /tmp/test_tts.wav
else
    test_failed "Cannot test TTS - Piper not available"
fi

# Test 8: Security
echo ""
echo "8. Testing Security..."

# Check file permissions
if [ -d "$BLACKBOX_DIR" ]; then
    PERMISSIONS=$(stat -c "%a" "$BLACKBOX_DIR")
    if [ "$PERMISSIONS" = "755" ]; then
        test_passed "Directory permissions correct"
    else
        test_warning "Directory permissions may be incorrect ($PERMISSIONS)"
    fi
fi

# Check for network interfaces (should be disabled)
if ip link show | grep -q "state UP" | grep -v "lo"; then
    test_warning "Network interfaces are active (offline mode recommended)"
else
    test_passed "Network interfaces disabled (offline mode)"
fi

# Test 9: Display
echo ""
echo "9. Testing Display..."

# Check display resolution
if command -v xrandr >/dev/null 2>&1; then
    RESOLUTION=$(xrandr | grep "*" | awk '{print $1}' | head -1)
    if [ "$RESOLUTION" = "1024x600" ]; then
        test_passed "Display resolution correct ($RESOLUTION)"
    else
        test_warning "Display resolution may be incorrect ($RESOLUTION)"
    fi
else
    test_warning "Cannot check display resolution (xrandr not available)"
fi

# Test 10: Final Summary
echo ""
echo "10. Test Summary"
echo "================"

# Count results
TOTAL_TESTS=$(grep -c "^[✓✗⚠]" "$TEST_RESULTS" || echo "0")
PASSED_TESTS=$(grep -c "^✓" "$TEST_RESULTS" || echo "0")
FAILED_TESTS=$(grep -c "^✗" "$TEST_RESULTS" || echo "0")
WARNING_TESTS=$(grep -c "^⚠" "$TEST_RESULTS" || echo "0")

echo "Total tests: $TOTAL_TESTS"
echo "Passed: $PASSED_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Warnings: $WARNING_TESTS"

if [ "$FAILED_TESTS" -eq 0 ]; then
    echo ""
    echo "🎉 All critical tests passed! BLACK BOX is ready to use."
    exit 0
else
    echo ""
    echo "❌ Some tests failed. Please check the results above."
    echo "Full test results saved to: $TEST_RESULTS"
    exit 1
fi
