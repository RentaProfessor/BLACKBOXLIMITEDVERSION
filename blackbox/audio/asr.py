"""
Automatic Speech Recognition module using Whisper.cpp
Optimized for NVIDIA Jetson Orin Nano with GPU acceleration
"""

import os
import subprocess
import tempfile
import threading
import time
import wave
import numpy as np
import sounddevice as sd
from typing import List, Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class WhisperASR:
    """GPU-optimized Whisper.cpp ASR with VAD and N-best output"""
    
    def __init__(self, model_path: str = "/mnt/nvme/blackbox/models/whisper-tiny.en.bin"):
        self.model_path = model_path
        self.sample_rate = 16000
        self.vad_window_ms = 700
        self.vad_threshold = 0.5
        self.temperature = 0.0
        self.temperature_fallback = 0.2
        self.n_best = 3
        
        # Audio recording state
        self.is_recording = False
        self.audio_buffer = []
        self.recording_thread = None
        
        # Verify model exists
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Whisper model not found at {model_path}")
    
    def start_recording(self) -> None:
        """Start continuous audio recording with VAD"""
        if self.is_recording:
            return
            
        self.is_recording = True
        self.audio_buffer = []
        
        def record_audio():
            try:
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype=np.float32,
                    blocksize=int(self.sample_rate * self.vad_window_ms / 1000),
                    callback=self._audio_callback
                ):
                    while self.is_recording:
                        time.sleep(0.1)
            except Exception as e:
                logger.error(f"Recording error: {e}")
        
        self.recording_thread = threading.Thread(target=record_audio, daemon=True)
        self.recording_thread.start()
        logger.info("Started audio recording")
    
    def stop_recording(self) -> np.ndarray:
        """Stop recording and return audio data"""
        if not self.is_recording:
            return np.array([])
            
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
        audio_data = np.concatenate(self.audio_buffer) if self.audio_buffer else np.array([])
        self.audio_buffer = []
        
        logger.info(f"Stopped recording, captured {len(audio_data)} samples")
        return audio_data
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback for audio input with VAD"""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        # Simple VAD based on RMS energy
        rms = np.sqrt(np.mean(indata**2))
        if rms > self.vad_threshold:
            self.audio_buffer.append(indata.copy())
    
    def transcribe(self, audio_data: np.ndarray) -> List[Dict[str, float]]:
        """
        Transcribe audio using Whisper.cpp with N-best output
        Returns list of transcriptions with confidence scores
        """
        if len(audio_data) == 0:
            return []
        
        # Save audio to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
            
            # Convert to 16-bit PCM
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
        
        try:
            # Run Whisper.cpp with GPU acceleration
            cmd = [
                "whisper-cpp/whisper",
                "-m", self.model_path,
                "-f", temp_path,
                "-t", str(self.temperature),
                "-n", str(self.n_best),
                "--no-timestamps",
                "--print-colors", "false"
            ]
            
            # Add GPU acceleration if available
            if self._check_gpu_available():
                cmd.extend(["--gpu", "1"])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10.0
            )
            
            if result.returncode != 0:
                logger.error(f"Whisper.cpp failed: {result.stderr}")
                return self._fallback_transcription(temp_path)
            
            # Parse N-best results
            transcriptions = self._parse_whisper_output(result.stdout)
            
            # If no good results, try with higher temperature
            if not transcriptions or max(t.get('confidence', 0) for t in transcriptions) < 0.7:
                logger.info("Trying fallback transcription with higher temperature")
                return self._fallback_transcription(temp_path)
            
            return transcriptions
            
        except subprocess.TimeoutExpired:
            logger.error("Whisper.cpp transcription timeout")
            return []
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return []
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _check_gpu_available(self) -> bool:
        """Check if GPU acceleration is available"""
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                timeout=2.0
            )
            return result.returncode == 0
        except:
            return False
    
    def _fallback_transcription(self, audio_path: str) -> List[Dict[str, float]]:
        """Fallback transcription with higher temperature"""
        try:
            cmd = [
                "whisper-cpp/whisper",
                "-m", self.model_path,
                "-f", audio_path,
                "-t", str(self.temperature_fallback),
                "-n", "1",
                "--no-timestamps",
                "--print-colors", "false"
            ]
            
            if self._check_gpu_available():
                cmd.extend(["--gpu", "1"])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=8.0
            )
            
            if result.returncode == 0:
                return self._parse_whisper_output(result.stdout)
            
        except Exception as e:
            logger.error(f"Fallback transcription failed: {e}")
        
        return []
    
    def _parse_whisper_output(self, output: str) -> List[Dict[str, float]]:
        """Parse Whisper.cpp output to extract transcriptions and confidence"""
        transcriptions = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if line.strip():
                # Extract text and confidence from Whisper output
                # Format: "text [confidence: 0.xx]"
                if '[' in line and ']' in line:
                    text = line.split('[')[0].strip()
                    conf_part = line.split('[')[1].split(']')[0]
                    if 'confidence:' in conf_part:
                        try:
                            confidence = float(conf_part.split('confidence:')[1].strip())
                            transcriptions.append({
                                'text': text,
                                'confidence': confidence
                            })
                        except ValueError:
                            transcriptions.append({
                                'text': text,
                                'confidence': 0.5
                            })
                else:
                    # No confidence score, assume medium confidence
                    transcriptions.append({
                        'text': line.strip(),
                        'confidence': 0.5
                    })
        
        return transcriptions
    
    def transcribe_realtime(self, duration_seconds: float = 5.0) -> List[Dict[str, float]]:
        """
        Record and transcribe audio in real-time
        Returns best transcription result
        """
        self.start_recording()
        time.sleep(duration_seconds)
        audio_data = self.stop_recording()
        
        if len(audio_data) == 0:
            return []
        
        transcriptions = self.transcribe(audio_data)
        
        # Return best transcription
        if transcriptions:
            best = max(transcriptions, key=lambda x: x.get('confidence', 0))
            return [best]
        
        return []


class AudioProcessor:
    """Audio preprocessing and enhancement for elderly speech patterns"""
    
    @staticmethod
    def enhance_elderly_speech(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """
        Apply audio enhancements for elderly speech patterns:
        - Reduce background noise
        - Enhance speech clarity
        - Handle stutters and pauses
        """
        # Simple noise reduction using spectral subtraction
        enhanced = AudioProcessor._spectral_subtraction(audio_data, sample_rate)
        
        # Normalize volume
        enhanced = AudioProcessor._normalize_volume(enhanced)
        
        # Remove long silences (common in elderly speech)
        enhanced = AudioProcessor._remove_long_silences(enhanced, sample_rate)
        
        return enhanced
    
    @staticmethod
    def _spectral_subtraction(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Simple spectral subtraction for noise reduction"""
        # Apply FFT
        fft = np.fft.fft(audio)
        magnitude = np.abs(fft)
        phase = np.angle(fft)
        
        # Estimate noise floor (first 10% of signal)
        noise_floor = np.mean(magnitude[:len(magnitude)//10])
        
        # Apply spectral subtraction
        enhanced_magnitude = magnitude - 0.3 * noise_floor
        enhanced_magnitude = np.maximum(enhanced_magnitude, 0.1 * magnitude)
        
        # Reconstruct signal
        enhanced_fft = enhanced_magnitude * np.exp(1j * phase)
        enhanced_audio = np.real(np.fft.ifft(enhanced_fft))
        
        return enhanced_audio.astype(np.float32)
    
    @staticmethod
    def _normalize_volume(audio: np.ndarray) -> np.ndarray:
        """Normalize audio volume to optimal range"""
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            # Normalize to 0.8 to avoid clipping
            return audio * (0.8 / max_val)
        return audio
    
    @staticmethod
    def _remove_long_silences(audio: np.ndarray, sample_rate: int, 
                            silence_threshold: float = 0.01,
                            max_silence_duration: float = 0.5) -> np.ndarray:
        """Remove long silences that might confuse ASR"""
        # Find silence regions
        silence_samples = int(max_silence_duration * sample_rate)
        window_size = int(0.1 * sample_rate)  # 100ms windows
        
        result = []
        i = 0
        
        while i < len(audio):
            window = audio[i:i+window_size]
            rms = np.sqrt(np.mean(window**2))
            
            if rms > silence_threshold:
                result.extend(window)
                i += window_size
            else:
                # Check if this is a long silence
                silence_start = i
                while i < len(audio) and np.sqrt(np.mean(audio[i:i+window_size]**2)) <= silence_threshold:
                    i += window_size
                
                silence_duration = (i - silence_start) / sample_rate
                if silence_duration < max_silence_duration:
                    # Keep short silences
                    result.extend(audio[silence_start:i])
                # Skip long silences
        
        return np.array(result, dtype=np.float32)
