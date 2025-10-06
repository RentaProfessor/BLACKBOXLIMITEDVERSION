#!/bin/bash

# BLACK BOX - Model installation script
# Downloads and installs Whisper.cpp, Piper TTS, and LLM models

set -e

BLACKBOX_DIR="/mnt/nvme/blackbox"
MODELS_DIR="$BLACKBOX_DIR/models"
WHISPER_DIR="$MODELS_DIR/whisper"
PIPER_DIR="$MODELS_DIR/piper"
LLM_DIR="$MODELS_DIR/llm"

echo "BLACK BOX - Installing AI models..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Create directories
mkdir -p "$MODELS_DIR"
mkdir -p "$WHISPER_DIR"
mkdir -p "$PIPER_DIR"
mkdir -p "$LLM_DIR"

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python3-pip \
    python3-dev \
    libasound2-dev \
    portaudio19-dev \
    libsndfile1-dev \
    ffmpeg \
    espeak-ng \
    espeak-ng-data

# Install Whisper.cpp
echo "Installing Whisper.cpp..."
cd /tmp
if [ -d "whisper.cpp" ]; then
    rm -rf whisper.cpp
fi

git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

# Build with GPU support for Jetson
make clean
make -j$(nproc) WHISPER_CUDA=1

# Install Whisper.cpp
cp whisper "$WHISPER_DIR/"
cp models/ggml-tiny.en.bin "$WHISPER_DIR/whisper-tiny.en.bin"
cp models/ggml-base.en.bin "$WHISPER_DIR/whisper-base.en.bin"

# Install Piper TTS
echo "Installing Piper TTS..."
cd /tmp
if [ -d "piper" ]; then
    rm -rf piper
fi

git clone https://github.com/rhasspy/piper.git
cd piper

# Build Piper
mkdir build
cd build
cmake ..
make -j$(nproc)

# Install Piper
cp src/piper "$PIPER_DIR/"

# Download Piper models
cd "$PIPER_DIR"
echo "Downloading Piper TTS models..."

# Download English model (smaller for Jetson)
wget -O en_US-lessac-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"

wget -O en_US-lessac-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install --upgrade pip
pip3 install \
    PySide6 \
    pysqlcipher3 \
    argon2-cffi \
    rapidfuzz \
    metaphone \
    sounddevice \
    simpleaudio \
    numpy \
    scipy \
    librosa \
    torch \
    torchaudio

# Install TensorRT-LLM (if available)
echo "Installing TensorRT-LLM..."
if command -v nvidia-smi &> /dev/null; then
    # Check if TensorRT is available
    if dpkg -l | grep -q tensorrt; then
        pip3 install tensorrt-llm
        echo "TensorRT-LLM installed successfully"
    else
        echo "TensorRT not found, skipping TensorRT-LLM installation"
    fi
else
    echo "NVIDIA GPU not detected, skipping TensorRT-LLM installation"
fi

# Download LLM models (placeholder - would need actual model files)
echo "Setting up LLM models directory..."
touch "$LLM_DIR/README.md"
echo "# LLM Models" > "$LLM_DIR/README.md"
echo "Place your LLM model files here:" >> "$LLM_DIR/README.md"
echo "- Llama 3.2 3B" >> "$LLM_DIR/README.md"
echo "- Phi 3.5 3B" >> "$LLM_DIR/README.md"
echo "- Gemma 2 2B" >> "$LLM_DIR/README.md"

# Set permissions
chown -R blackbox:blackbox "$BLACKBOX_DIR"
chmod -R 755 "$BLACKBOX_DIR"

# Create symlinks for easy access
ln -sf "$WHISPER_DIR/whisper" /usr/local/bin/whisper-cpp
ln -sf "$PIPER_DIR/piper" /usr/local/bin/piper

echo "Model installation complete!"
echo "Installed models:"
echo "- Whisper.cpp: $WHISPER_DIR"
echo "- Piper TTS: $PIPER_DIR"
echo "- LLM models: $LLM_DIR"

# Test installations
echo "Testing installations..."
if [ -f "$WHISPER_DIR/whisper" ]; then
    echo "✓ Whisper.cpp installed successfully"
else
    echo "✗ Whisper.cpp installation failed"
fi

if [ -f "$PIPER_DIR/piper" ]; then
    echo "✓ Piper TTS installed successfully"
else
    echo "✗ Piper TTS installation failed"
fi

echo "Installation complete!"
