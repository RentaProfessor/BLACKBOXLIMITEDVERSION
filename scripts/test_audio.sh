#!/bin/bash

# BLACK BOX - Audio system test script
# Tests aplay test tone, record 3s and play back

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
TEST_RESULTS="$BLACKBOX_DIR/logs/audio_test.log"

echo "BLACK BOX - Audio System Test"
echo "============================="

# Create test results file
mkdir -p "$(dirname "$TEST_RESULTS")"
echo "BLACK BOX Audio Test Results - $(date)" > "$TEST_RESULTS"
echo "=====================================" >> "$TEST_RESULTS"

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

# Test 1: Audio device detection
echo ""
echo "1. Testing Audio Device Detection..."

# Check output devices
if aplay -l | grep -q "card"; then
    OUTPUT_DEVICES=$(aplay -l | grep "card" | wc -l)
    test_passed "Audio output devices detected ($OUTPUT_DEVICES devices)"
    
    # Show device details
    echo "Output devices:" | tee -a "$TEST_RESULTS"
    aplay -l | tee -a "$TEST_RESULTS"
else
    test_failed "No audio output devices found"
fi

# Check input devices
if arecord -l | grep -q "card"; then
    INPUT_DEVICES=$(arecord -l | grep "card" | wc -l)
    test_passed "Audio input devices detected ($INPUT_DEVICES devices)"
    
    # Show device details
    echo "Input devices:" | tee -a "$TEST_RESULTS"
    arecord -l | tee -a "$TEST_RESULTS"
else
    test_failed "No audio input devices found"
fi

# Test 2: Audio output test
echo ""
echo "2. Testing Audio Output..."

# Test with built-in test tone
if command -v speaker-test >/dev/null 2>&1; then
    echo "Testing with speaker-test..."
    if timeout 3 speaker-test -c 2 -t sine -f 1000 -l 1 >/dev/null 2>&1; then
        test_passed "Audio output test passed (speaker-test)"
    else
        test_warning "Audio output test failed (speaker-test)"
    fi
else
    test_warning "speaker-test not available"
fi

# Test with aplay
if command -v aplay >/dev/null 2>&1; then
    echo "Testing with aplay..."
    
    # Create a test tone using sox if available
    if command -v sox >/dev/null 2>&1; then
        sox -n /tmp/test_tone.wav synth 1 sine 440
        if timeout 5 aplay /tmp/test_tone.wav >/dev/null 2>&1; then
            test_passed "Audio output test passed (aplay)"
        else
            test_warning "Audio output test failed (aplay)"
        fi
        rm -f /tmp/test_tone.wav
    else
        # Try with built-in test file
        if [ -f "/usr/share/sounds/alsa/Front_Left.wav" ]; then
            if timeout 5 aplay /usr/share/sounds/alsa/Front_Left.wav >/dev/null 2>&1; then
                test_passed "Audio output test passed (built-in test file)"
            else
                test_warning "Audio output test failed (built-in test file)"
            fi
        else
            test_warning "No test audio files available"
        fi
    fi
else
    test_failed "aplay not available"
fi

# Test 3: Audio input test
echo ""
echo "3. Testing Audio Input..."

if command -v arecord >/dev/null 2>&1; then
    echo "Recording 3 seconds of audio..."
    
    # Record 3 seconds of audio
    if timeout 5 arecord -f S16_LE -r 16000 -c 1 -d 3 /tmp/test_recording.wav >/dev/null 2>&1; then
        if [ -f "/tmp/test_recording.wav" ] && [ -s "/tmp/test_recording.wav" ]; then
            FILE_SIZE=$(stat -c%s "/tmp/test_recording.wav")
            test_passed "Audio input test passed (recorded $FILE_SIZE bytes)"
            
            # Test playback of recorded audio
            echo "Playing back recorded audio..."
            if timeout 5 aplay /tmp/test_recording.wav >/dev/null 2>&1; then
                test_passed "Audio input playback test passed"
            else
                test_warning "Audio input playback test failed"
            fi
            
            # Clean up
            rm -f /tmp/test_recording.wav
        else
            test_failed "Audio input test failed (no data recorded)"
        fi
    else
        test_failed "Audio input test failed (recording timeout)"
    fi
else
    test_failed "arecord not available"
fi

# Test 4: Audio device configuration
echo ""
echo "4. Testing Audio Device Configuration..."

# Check if audio configuration exists
if [ -f "$BLACKBOX_DIR/config/audio.json" ]; then
    test_passed "Audio configuration file exists"
    
    # Validate JSON
    if python3 -c "import json; json.load(open('$BLACKBOX_DIR/config/audio.json'))" 2>/dev/null; then
        test_passed "Audio configuration file is valid JSON"
    else
        test_failed "Audio configuration file is invalid JSON"
    fi
else
    test_warning "Audio configuration file not found"
fi

# Test 5: Audio probe functionality
echo ""
echo "5. Testing Audio Probe Functionality..."

if [ -f "$BLACKBOX_DIR/blackbox/audio/probe.py" ]; then
    cd "$BLACKBOX_DIR"
    if python3 -c "
from blackbox.audio.probe import AudioDeviceProbe
probe = AudioDeviceProbe()
devices = probe.probe_devices()
print('Audio probe test completed')
" 2>/dev/null; then
        test_passed "Audio probe functionality test passed"
    else
        test_warning "Audio probe functionality test failed"
    fi
else
    test_warning "Audio probe script not found"
fi

# Test 6: ALSA configuration
echo ""
echo "6. Testing ALSA Configuration..."

# Check ALSA configuration
if [ -f "/etc/asound.conf" ]; then
    test_passed "ALSA configuration file exists"
else
    test_warning "ALSA configuration file not found"
fi

# Check PulseAudio
if systemctl is-active --quiet pulseaudio; then
    test_passed "PulseAudio service is running"
else
    test_warning "PulseAudio service is not running"
fi

# Test 7: Audio permissions
echo ""
echo "7. Testing Audio Permissions..."

# Check if user is in audio group
if groups | grep -q audio; then
    test_passed "User is in audio group"
else
    test_warning "User is not in audio group"
fi

# Check device permissions
if [ -d "/dev/snd" ]; then
    DEVICE_PERMISSIONS=$(ls -la /dev/snd/ | head -5)
    echo "Audio device permissions:" | tee -a "$TEST_RESULTS"
    echo "$DEVICE_PERMISSIONS" | tee -a "$TEST_RESULTS"
    test_passed "Audio device directory accessible"
else
    test_failed "Audio device directory not found"
fi

# Test 8: Performance test
echo ""
echo "8. Testing Audio Performance..."

# Test latency
if command -v aplay >/dev/null 2>&1 && command -v arecord >/dev/null 2>&1; then
    echo "Testing audio latency..."
    
    # Create a short test tone
    if command -v sox >/dev/null 2>&1; then
        sox -n /tmp/latency_test.wav synth 0.1 sine 1000
        
        # Measure playback time
        START_TIME=$(date +%s.%N)
        aplay /tmp/latency_test.wav >/dev/null 2>&1
        END_TIME=$(date +%s.%N)
        PLAYBACK_TIME=$(echo "$END_TIME - $START_TIME" | bc -l)
        
        if (( $(echo "$PLAYBACK_TIME < 0.5" | bc -l) )); then
            test_passed "Audio latency test passed (${PLAYBACK_TIME}s)"
        else
            test_warning "Audio latency test failed (${PLAYBACK_TIME}s > 0.5s)"
        fi
        
        rm -f /tmp/latency_test.wav
    else
        test_warning "sox not available for latency test"
    fi
else
    test_warning "Audio tools not available for performance test"
fi

# Test Summary
echo ""
echo "Audio Test Summary"
echo "=================="

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
    echo "🎉 All critical audio tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some audio tests failed. Please check the results above."
    echo "Full test results saved to: $TEST_RESULTS"
    exit 1
fi
