"""
Text-to-Speech module using Piper TTS
Optimized for low-latency audio feedback and elderly users
"""

import os
import subprocess
import tempfile
import threading
import time
import wave
import numpy as np
import sounddevice as sd
from typing import Optional, List
import logging
import queue

logger = logging.getLogger(__name__)

class PiperTTS:
    """Piper TTS with pre-loaded model and audio streaming"""
    
    def __init__(self, model_path: str = "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx",
                 config_path: str = "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx.json"):
        self.model_path = model_path
        self.config_path = config_path
        self.sample_rate = 22050
        self.is_loaded = False
        self.audio_queue = queue.Queue()
        self.playback_thread = None
        self.is_playing = False
        
        # Pre-load model for faster response
        self._load_model()
    
    def _load_model(self) -> None:
        """Pre-load Piper model to keep it warm"""
        try:
            # Test model loading with a short phrase
            test_text = "Hello"
            self._synthesize_to_file(test_text, "/tmp/piper_test.wav")
            
            if os.path.exists("/tmp/piper_test.wav"):
                os.unlink("/tmp/piper_test.wav")
                self.is_loaded = True
                logger.info("Piper TTS model loaded successfully")
            else:
                logger.error("Failed to load Piper TTS model")
                
        except Exception as e:
            logger.error(f"Error loading Piper TTS model: {e}")
            self.is_loaded = False
    
    def _synthesize_to_file(self, text: str, output_path: str) -> bool:
        """Synthesize text to WAV file using Piper"""
        try:
            cmd = [
                "piper",
                "--model", self.model_path,
                "--config", self.config_path,
                "--output_file", output_path
            ]
            
            # Use echo to pipe text to piper
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=5.0)
            
            if process.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                logger.error(f"Piper synthesis failed: {stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Piper synthesis timeout")
            return False
        except Exception as e:
            logger.error(f"Piper synthesis error: {e}")
            return False
    
    def speak(self, text: str, blocking: bool = False) -> None:
        """
        Convert text to speech and play it
        Args:
            text: Text to synthesize
            blocking: If True, wait for speech to complete
        """
        if not self.is_loaded:
            logger.warning("TTS model not loaded, skipping speech")
            return
        
        if blocking:
            self._speak_blocking(text)
        else:
            # Queue for non-blocking playback
            self.audio_queue.put(text)
            if not self.is_playing:
                self._start_playback_thread()
    
    def _speak_blocking(self, text: str) -> None:
        """Synthesize and play text synchronously"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            if self._synthesize_to_file(text, temp_path):
                self._play_audio_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def _start_playback_thread(self) -> None:
        """Start background thread for audio playback"""
        if self.playback_thread and self.playback_thread.is_alive():
            return
        
        def playback_worker():
            self.is_playing = True
            try:
                while not self.audio_queue.empty():
                    text = self.audio_queue.get_nowait()
                    self._speak_blocking(text)
                    self.audio_queue.task_done()
            except queue.Empty:
                pass
            finally:
                self.is_playing = False
        
        self.playback_thread = threading.Thread(target=playback_worker, daemon=True)
        self.playback_thread.start()
    
    def _play_audio_file(self, file_path: str) -> None:
        """Play WAV file through ALSA"""
        try:
            # Read WAV file
            with wave.open(file_path, 'rb') as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
            
            # Convert to numpy array
            if sample_width == 2:
                audio_data = np.frombuffer(frames, dtype=np.int16)
            elif sample_width == 4:
                audio_data = np.frombuffer(frames, dtype=np.int32)
            else:
                logger.error(f"Unsupported sample width: {sample_width}")
                return
            
            # Convert to float32 and normalize
            audio_data = audio_data.astype(np.float32) / 32767.0
            
            # Resample if necessary
            if sample_rate != self.sample_rate:
                audio_data = self._resample_audio(audio_data, sample_rate, self.sample_rate)
            
            # Play through ALSA
            sd.play(audio_data, samplerate=self.sample_rate, channels=channels)
            sd.wait()  # Wait for playback to complete
            
        except Exception as e:
            logger.error(f"Error playing audio file: {e}")
    
    def _resample_audio(self, audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Simple resampling using linear interpolation"""
        if orig_sr == target_sr:
            return audio_data
        
        ratio = target_sr / orig_sr
        new_length = int(len(audio_data) * ratio)
        
        # Linear interpolation
        old_indices = np.linspace(0, len(audio_data) - 1, new_length)
        resampled = np.interp(old_indices, np.arange(len(audio_data)), audio_data)
        
        return resampled.astype(np.float32)
    
    def play_beep(self, count: int = 1, duration: float = 0.2, frequency: float = 800.0) -> None:
        """
        Generate and play beep sounds for audio feedback
        Args:
            count: Number of beeps
            duration: Duration of each beep in seconds
            frequency: Frequency of beep in Hz
        """
        def generate_beep(freq: float, duration: float, sample_rate: int) -> np.ndarray:
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            beep = 0.3 * np.sin(2 * np.pi * freq * t)
            # Apply fade in/out to avoid clicks
            fade_samples = int(0.01 * sample_rate)  # 10ms fade
            beep[:fade_samples] *= np.linspace(0, 1, fade_samples)
            beep[-fade_samples:] *= np.linspace(1, 0, fade_samples)
            return beep.astype(np.float32)
        
        try:
            for i in range(count):
                beep = generate_beep(frequency, duration, self.sample_rate)
                sd.play(beep, samplerate=self.sample_rate)
                sd.wait()
                
                # Short pause between beeps
                if i < count - 1:
                    time.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error playing beep: {e}")
    
    def speak_status(self, status: str) -> None:
        """Speak predefined status messages for elderly users"""
        status_messages = {
            'recording_start': "Recording started. Please speak now.",
            'recording_stop': "Recording stopped.",
            'saved': "Password saved successfully.",
            'retrieved': "Password retrieved.",
            'error': "Sorry, I didn't understand. Please try again.",
            'confirm': "Please confirm this is correct.",
            'locked': "Vault is locked. Please enter your passphrase.",
            'unlocked': "Vault unlocked.",
            'timeout': "Session timed out. Please try again."
        }
        
        message = status_messages.get(status, status)
        self.speak(message, blocking=False)
    
    def speak_password(self, password: str, confirm: bool = True) -> None:
        """
        Speak password with confirmation for security
        Args:
            password: Password to speak
            confirm: Whether to ask for confirmation first
        """
        if confirm:
            self.speak("I will now speak your password. Is this correct?", blocking=True)
            # In a real implementation, you'd wait for user confirmation here
            # For now, we'll add a delay
            time.sleep(2)
        
        # Speak password with pauses between characters for clarity
        password_spoken = " ".join(password)
        self.speak(password_spoken, blocking=True)
    
    def stop(self) -> None:
        """Stop all TTS operations"""
        try:
            sd.stop()
            self.is_playing = False
            # Clear audio queue
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error stopping TTS: {e}")


class AudioFeedback:
    """Audio feedback system for user interactions"""
    
    def __init__(self, tts: PiperTTS):
        self.tts = tts
    
    def recording_start(self) -> None:
        """Audio feedback for recording start"""
        self.tts.play_beep(count=1, duration=0.3, frequency=800)
        self.tts.speak_status('recording_start')
    
    def recording_stop(self) -> None:
        """Audio feedback for recording stop"""
        self.tts.play_beep(count=2, duration=0.2, frequency=600)
        self.tts.speak_status('recording_stop')
    
    def success(self) -> None:
        """Audio feedback for successful operation"""
        self.tts.play_beep(count=3, duration=0.15, frequency=1000)
        self.tts.speak_status('saved')
    
    def error(self) -> None:
        """Audio feedback for error"""
        self.tts.play_beep(count=1, duration=0.5, frequency=400)
        self.tts.speak_status('error')
    
    def confirm(self) -> None:
        """Audio feedback for confirmation needed"""
        self.tts.play_beep(count=2, duration=0.2, frequency=700)
        self.tts.speak_status('confirm')


class AudioManager:
    """Centralized audio management for the BLACK BOX system"""
    
    def __init__(self):
        self.tts = PiperTTS()
        self.feedback = AudioFeedback(self.tts)
        self.is_initialized = False
        
        # Initialize audio system
        self._setup_audio()
    
    def _setup_audio(self) -> None:
        """Setup ALSA audio system for Jetson"""
        try:
            # Test audio output
            test_audio = np.zeros(int(0.1 * self.tts.sample_rate), dtype=np.float32)
            sd.play(test_audio, samplerate=self.tts.sample_rate)
            sd.wait()
            
            self.is_initialized = True
            logger.info("Audio system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize audio system: {e}")
            self.is_initialized = False
    
    def speak(self, text: str, blocking: bool = False) -> None:
        """Speak text using TTS"""
        if self.is_initialized:
            self.tts.speak(text, blocking)
    
    def play_beep(self, count: int = 1, duration: float = 0.2, frequency: float = 800.0) -> None:
        """Play beep sound"""
        if self.is_initialized:
            self.tts.play_beep(count, duration, frequency)
    
    def recording_start(self) -> None:
        """Audio feedback for recording start"""
        if self.is_initialized:
            self.feedback.recording_start()
    
    def recording_stop(self) -> None:
        """Audio feedback for recording stop"""
        if self.is_initialized:
            self.feedback.recording_stop()
    
    def success(self) -> None:
        """Audio feedback for success"""
        if self.is_initialized:
            self.feedback.success()
    
    def error(self) -> None:
        """Audio feedback for error"""
        if self.is_initialized:
            self.feedback.error()
    
    def confirm(self) -> None:
        """Audio feedback for confirmation"""
        if self.is_initialized:
            self.feedback.confirm()
    
    def shutdown(self) -> None:
        """Shutdown audio system"""
        if self.is_initialized:
            self.tts.stop()
            logger.info("Audio system shutdown complete")
