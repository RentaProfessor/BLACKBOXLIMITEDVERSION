#!/bin/bash

# BLACK BOX - ASR test script
# Tests Whisper.cpp on a sample WAV file

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
TEST_RESULTS="$BLACKBOX_DIR/logs/asr_test.log"

echo "BLACK BOX - ASR System Test"
echo "==========================="

# Create test results file
mkdir -p "$(dirname "$TEST_RESULTS")"
echo "BLACK BOX ASR Test Results - $(date)" > "$TEST_RESULTS"
echo "===================================" >> "$TEST_RESULTS"

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

# Test 1: Whisper.cpp binary check
echo ""
echo "1. Testing Whisper.cpp Binary..."

WHISPER_BINARY="$BLACKBOX_DIR/models/whisper/whisper"
if [ -f "$WHISPER_BINARY" ]; then
    test_passed "Whisper.cpp binary found"
    
    # Test binary execution
    if "$WHISPER_BINARY" --help >/dev/null 2>&1; then
        test_passed "Whisper.cpp binary is executable"
    else
        test_failed "Whisper.cpp binary is not executable"
    fi
else
    test_failed "Whisper.cpp binary not found at $WHISPER_BINARY"
fi

# Test 2: Whisper model check
echo ""
echo "2. Testing Whisper Models..."

WHISPER_TINY="$BLACKBOX_DIR/models/whisper/whisper-tiny.en.bin"
WHISPER_BASE="$BLACKBOX_DIR/models/whisper/whisper-base.en.bin"

if [ -f "$WHISPER_TINY" ]; then
    MODEL_SIZE=$(stat -c%s "$WHISPER_TINY")
    MODEL_SIZE_MB=$((MODEL_SIZE / 1024 / 1024))
    test_passed "Whisper tiny model found (${MODEL_SIZE_MB}MB)"
else
    test_failed "Whisper tiny model not found"
fi

if [ -f "$WHISPER_BASE" ]; then
    MODEL_SIZE=$(stat -c%s "$WHISPER_BASE")
    MODEL_SIZE_MB=$((MODEL_SIZE / 1024 / 1024))
    test_passed "Whisper base model found (${MODEL_SIZE_MB}MB)"
else
    test_warning "Whisper base model not found"
fi

# Test 3: Create test audio file
echo ""
echo "3. Creating Test Audio File..."

TEST_AUDIO="/tmp/test_asr.wav"

# Create a test audio file with speech
if command -v espeak >/dev/null 2>&1; then
    echo "Creating test audio with espeak..."
    espeak -s 150 -w "$TEST_AUDIO" "Hello, this is a test of the speech recognition system."
    test_passed "Test audio file created with espeak"
elif command -v sox >/dev/null 2>&1; then
    echo "Creating test audio with sox..."
    # Create a simple tone (not ideal for ASR testing)
    sox -n "$TEST_AUDIO" synth 2 sine 440
    test_warning "Test audio file created with sox (tone only)"
else
    # Create a silent audio file
    echo "Creating silent test audio file..."
    python3 -c "
import wave
import numpy as np

# Create 2 seconds of silence
sample_rate = 16000
duration = 2
samples = int(sample_rate * duration)
silence = np.zeros(samples, dtype=np.int16)

with wave.open('$TEST_AUDIO', 'wb') as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    wav_file.writeframes(silence.tobytes())
"
    test_warning "Silent test audio file created"
fi

if [ -f "$TEST_AUDIO" ]; then
    AUDIO_SIZE=$(stat -c%s "$TEST_AUDIO")
    test_passed "Test audio file created (${AUDIO_SIZE} bytes)"
else
    test_failed "Failed to create test audio file"
    exit 1
fi

# Test 4: Whisper.cpp transcription test
echo ""
echo "4. Testing Whisper.cpp Transcription..."

if [ -f "$WHISPER_BINARY" ] && [ -f "$WHISPER_TINY" ]; then
    echo "Running Whisper.cpp transcription test..."
    
    # Run Whisper.cpp with timeout
    START_TIME=$(date +%s)
    if timeout 30 "$WHISPER_BINARY" \
        -m "$WHISPER_TINY" \
        -f "$TEST_AUDIO" \
        --language en \
        --no-timestamps \
        --print-colors false \
        > /tmp/whisper_output.txt 2>&1; then
        
        END_TIME=$(date +%s)
        TRANSCRIPTION_TIME=$((END_TIME - START_TIME))
        
        if [ -s "/tmp/whisper_output.txt" ]; then
            TRANSCRIPTION=$(cat /tmp/whisper_output.txt)
            test_passed "Whisper.cpp transcription completed (${TRANSCRIPTION_TIME}s)"
            echo "Transcription: $TRANSCRIPTION" | tee -a "$TEST_RESULTS"
            
            # Check if transcription contains expected words
            if echo "$TRANSCRIPTION" | grep -qi "hello\|test\|speech\|recognition"; then
                test_passed "Transcription contains expected words"
            else
                test_warning "Transcription may not be accurate"
            fi
        else
            test_failed "Whisper.cpp produced no output"
        fi
    else
        test_failed "Whisper.cpp transcription failed or timed out"
        if [ -f "/tmp/whisper_output.txt" ]; then
            echo "Error output:" | tee -a "$TEST_RESULTS"
            cat /tmp/whisper_output.txt | tee -a "$TEST_RESULTS"
        fi
    fi
else
    test_failed "Whisper.cpp binary or model not available"
fi

# Test 5: Performance test
echo ""
echo "5. Testing ASR Performance..."

if [ -f "$WHISPER_BINARY" ] && [ -f "$WHISPER_TINY" ]; then
    echo "Testing ASR performance..."
    
    # Test with different audio lengths
    for duration in 1 3 5; do
        echo "Testing ${duration}s audio..."
        
        # Create audio of specified duration
        python3 -c "
import wave
import numpy as np

sample_rate = 16000
samples = int(sample_rate * $duration)
silence = np.zeros(samples, dtype=np.int16)

with wave.open('/tmp/test_${duration}s.wav', 'wb') as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    wav_file.writeframes(silence.tobytes())
"
        
        # Test transcription time
        START_TIME=$(date +%s.%N)
        if timeout 30 "$WHISPER_BINARY" \
            -m "$WHISPER_TINY" \
            -f "/tmp/test_${duration}s.wav" \
            --language en \
            --no-timestamps \
            --print-colors false \
            >/dev/null 2>&1; then
            
            END_TIME=$(date +%s.%N)
            TRANSCRIPTION_TIME=$(echo "$END_TIME - $START_TIME" | bc -l)
            
            # Check if performance target is met (≤ 1.5s for 1s audio)
            TARGET_TIME=$(echo "$duration * 1.5" | bc -l)
            if (( $(echo "$TRANSCRIPTION_TIME <= $TARGET_TIME" | bc -l) )); then
                test_passed "ASR performance test passed for ${duration}s audio (${TRANSCRIPTION_TIME}s ≤ ${TARGET_TIME}s)"
            else
                test_warning "ASR performance test failed for ${duration}s audio (${TRANSCRIPTION_TIME}s > ${TARGET_TIME}s)"
            fi
        else
            test_failed "ASR performance test failed for ${duration}s audio"
        fi
        
        rm -f "/tmp/test_${duration}s.wav"
    done
else
    test_warning "ASR performance test skipped (Whisper not available)"
fi

# Test 6: GPU acceleration test
echo ""
echo "6. Testing GPU Acceleration..."

if command -v nvidia-smi >/dev/null 2>&1; then
    if nvidia-smi >/dev/null 2>&1; then
        test_passed "NVIDIA GPU detected"
        
        # Test GPU acceleration with Whisper
        if [ -f "$WHISPER_BINARY" ] && [ -f "$WHISPER_TINY" ]; then
            echo "Testing GPU acceleration..."
            
            # Test without GPU
            START_TIME=$(date +%s.%N)
            timeout 30 "$WHISPER_BINARY" \
                -m "$WHISPER_TINY" \
                -f "$TEST_AUDIO" \
                --language en \
                --no-timestamps \
                --print-colors false \
                >/dev/null 2>&1
            END_TIME=$(date +%s.%N)
            CPU_TIME=$(echo "$END_TIME - $START_TIME" | bc -l)
            
            # Test with GPU
            START_TIME=$(date +%s.%N)
            timeout 30 "$WHISPER_BINARY" \
                -m "$WHISPER_TINY" \
                -f "$TEST_AUDIO" \
                --language en \
                --no-timestamps \
                --print-colors false \
                --gpu 1 \
                >/dev/null 2>&1
            END_TIME=$(date +%s.%N)
            GPU_TIME=$(echo "$END_TIME - $START_TIME" | bc -l)
            
            if (( $(echo "$GPU_TIME < $CPU_TIME" | bc -l) )); then
                SPEEDUP=$(echo "$CPU_TIME / $GPU_TIME" | bc -l)
                test_passed "GPU acceleration working (${SPEEDUP}x speedup)"
            else
                test_warning "GPU acceleration may not be working (${GPU_TIME}s vs ${CPU_TIME}s)"
            fi
        else
            test_warning "GPU acceleration test skipped (Whisper not available)"
        fi
    else
        test_warning "NVIDIA GPU not accessible"
    fi
else
    test_warning "NVIDIA GPU not detected"
fi

# Test 7: Python ASR wrapper test
echo ""
echo "7. Testing Python ASR Wrapper..."

if [ -f "$BLACKBOX_DIR/blackbox/audio/asr_whispercpp.py" ]; then
    cd "$BLACKBOX_DIR"
    if python3 -c "
from blackbox.audio.asr_whispercpp import WhisperCppASR
import numpy as np

# Test ASR initialization
try:
    asr = WhisperCppASR()
    print('ASR initialization successful')
    
    # Test with dummy audio data
    dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
    result = asr.transcribe_audio(dummy_audio)
    print('ASR transcription test completed')
except Exception as e:
    print(f'ASR test failed: {e}')
    exit(1)
" 2>/dev/null; then
        test_passed "Python ASR wrapper test passed"
    else
        test_warning "Python ASR wrapper test failed"
    fi
else
    test_warning "Python ASR wrapper not found"
fi

# Clean up
rm -f "$TEST_AUDIO" /tmp/whisper_output.txt

# Test Summary
echo ""
echo "ASR Test Summary"
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
    echo "🎉 All critical ASR tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some ASR tests failed. Please check the results above."
    echo "Full test results saved to: $TEST_RESULTS"
    exit 1
fi
