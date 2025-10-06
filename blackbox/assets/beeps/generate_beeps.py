#!/usr/bin/env python3
"""
Generate beep sound files for audio feedback
Creates short WAV files for different feedback types
"""

import numpy as np
import wave
import os
from pathlib import Path

def generate_beep(frequency: float, duration: float, sample_rate: int = 22050) -> np.ndarray:
    """Generate a beep tone"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    beep = 0.3 * np.sin(2 * np.pi * frequency * t)
    
    # Apply fade in/out to avoid clicks
    fade_samples = int(0.01 * sample_rate)  # 10ms fade
    beep[:fade_samples] *= np.linspace(0, 1, fade_samples)
    beep[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    
    return beep.astype(np.float32)

def save_wav_file(file_path: str, audio_data: np.ndarray, sample_rate: int = 22050):
    """Save audio data to WAV file"""
    # Convert to int16
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    # Write WAV file
    with wave.open(file_path, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())

def main():
    """Generate all beep files"""
    # Create assets directory
    assets_dir = Path(__file__).parent
    assets_dir.mkdir(exist_ok=True)
    
    sample_rate = 22050
    
    # Recording start beep (1 beep, 800Hz, 0.3s)
    print("Generating recording start beep...")
    beep = generate_beep(800, 0.3, sample_rate)
    save_wav_file(assets_dir / "recording_start.wav", beep, sample_rate)
    
    # Recording stop beep (2 beeps, 600Hz, 0.2s each)
    print("Generating recording stop beep...")
    beep1 = generate_beep(600, 0.2, sample_rate)
    beep2 = generate_beep(600, 0.2, sample_rate)
    silence = np.zeros(int(0.1 * sample_rate), dtype=np.float32)  # 100ms silence
    beep_sequence = np.concatenate([beep1, silence, beep2])
    save_wav_file(assets_dir / "recording_stop.wav", beep_sequence, sample_rate)
    
    # Success beep (3 beeps, 1000Hz, 0.15s each)
    print("Generating success beep...")
    beep1 = generate_beep(1000, 0.15, sample_rate)
    beep2 = generate_beep(1000, 0.15, sample_rate)
    beep3 = generate_beep(1000, 0.15, sample_rate)
    silence = np.zeros(int(0.1 * sample_rate), dtype=np.float32)  # 100ms silence
    beep_sequence = np.concatenate([beep1, silence, beep2, silence, beep3])
    save_wav_file(assets_dir / "success.wav", beep_sequence, sample_rate)
    
    # Error beep (1 beep, 400Hz, 0.5s)
    print("Generating error beep...")
    beep = generate_beep(400, 0.5, sample_rate)
    save_wav_file(assets_dir / "error.wav", beep, sample_rate)
    
    # Confirm beep (2 beeps, 700Hz, 0.2s each)
    print("Generating confirm beep...")
    beep1 = generate_beep(700, 0.2, sample_rate)
    beep2 = generate_beep(700, 0.2, sample_rate)
    silence = np.zeros(int(0.1 * sample_rate), dtype=np.float32)  # 100ms silence
    beep_sequence = np.concatenate([beep1, silence, beep2])
    save_wav_file(assets_dir / "confirm.wav", beep_sequence, sample_rate)
    
    print("All beep files generated successfully!")
    print(f"Files saved to: {assets_dir}")

if __name__ == "__main__":
    main()
