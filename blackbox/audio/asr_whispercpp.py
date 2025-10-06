"""
Robust Whisper.cpp wrapper with proper flags and error handling
Records PCM to temp WAV, runs whisper.cpp with optimized flags
Returns N-best transcripts + confidences with retry logic
"""

import os
import tempfile
import subprocess
import threading
import time
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
import wave

logger = logging.getLogger(__name__)

class WhisperCppASR:
    """Robust Whisper.cpp ASR wrapper"""
    
    def __init__(self, model_path: str = "/mnt/nvme/blackbox/models/whisper/whisper-tiny.en.bin"):
        self.model_path = model_path
        self.whisper_binary = "/mnt/nvme/blackbox/models/whisper/whisper"
        self.sample_rate = 16000
        self.max_segment_duration = 8.0  # 8 seconds max
        self.min_segment_duration = 1.0  # 1 second min
        
        # Verify model and binary exist
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Whisper model not found at {self.model_path}")
        
        if not os.path.exists(self.whisper_binary):
            raise FileNotFoundError(f"Whisper binary not found at {self.whisper_binary}")
    
    def transcribe_audio(self, audio_data: np.ndarray, 
                        sample_rate: int = 16000,
                        max_retries: int = 2) -> List[Dict[str, float]]:
        """
        Transcribe audio using Whisper.cpp with robust error handling
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate of audio
            max_retries: Maximum number of retry attempts
        Returns:
            List of transcription results with confidence scores
        """
        if len(audio_data) == 0:
            logger.warning("Empty audio data provided")
            return []
        
        # Validate audio duration
        duration = len(audio_data) / sample_rate
        if duration < self.min_segment_duration:
            logger.warning(f"Audio too short: {duration:.2f}s < {self.min_segment_duration}s")
            return []
        
        if duration > self.max_segment_duration:
            logger.warning(f"Audio too long: {duration:.2f}s > {self.max_segment_duration}s")
            # Truncate to max duration
            max_samples = int(self.max_segment_duration * sample_rate)
            audio_data = audio_data[:max_samples]
        
        # Try transcription with retries
        for attempt in range(max_retries + 1):
            try:
                result = self._transcribe_with_whisper(audio_data, sample_rate, attempt)
                if result:
                    return result
            except Exception as e:
                logger.error(f"Transcription attempt {attempt + 1} failed: {e}")
                if attempt == max_retries:
                    logger.error("All transcription attempts failed")
                    return []
        
        return []
    
    def _transcribe_with_whisper(self, audio_data: np.ndarray, 
                                sample_rate: int, 
                                attempt: int) -> List[Dict[str, float]]:
        """Transcribe audio with Whisper.cpp"""
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Write audio to WAV file
            self._write_wav_file(temp_path, audio_data, sample_rate)
            
            # Build Whisper.cpp command
            cmd = self._build_whisper_command(temp_path, attempt)
            
            # Run Whisper.cpp
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15.0  # 15 second timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Whisper.cpp failed (attempt {attempt + 1}): {result.stderr}")
                return []
            
            # Parse output
            transcriptions = self._parse_whisper_output(result.stdout)
            
            # Check if we need to retry with higher temperature
            if attempt == 0 and transcriptions:
                best_confidence = max(t.get('confidence', 0) for t in transcriptions)
                if best_confidence < 0.7:
                    logger.info(f"Low confidence ({best_confidence:.2f}), will retry with higher temperature")
                    return []  # Force retry
            
            return transcriptions
            
        except subprocess.TimeoutExpired:
            logger.error(f"Whisper.cpp timeout (attempt {attempt + 1})")
            return []
        except Exception as e:
            logger.error(f"Error in transcription (attempt {attempt + 1}): {e}")
            return []
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def _build_whisper_command(self, audio_path: str, attempt: int) -> List[str]:
        """Build Whisper.cpp command with appropriate flags"""
        
        # Base command
        cmd = [
            self.whisper_binary,
            "-m", self.model_path,
            "-f", audio_path,
            "--language", "en",
            "--threads", str(os.cpu_count() or 4),
            "--best-of", "5",
            "--beam-size", "5",
            "--vad",
            "--no-timestamps",
            "--print-colors", "false"
        ]
        
        # Temperature based on attempt
        if attempt == 0:
            cmd.extend(["-t", "0.0"])  # Low temperature for first attempt
        else:
            cmd.extend(["-t", "0.2"])  # Slightly higher temperature for retry
        
        # Add GPU acceleration if available
        if self._check_gpu_available():
            cmd.extend(["--gpu", "1"])
        
        return cmd
    
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
    
    def _write_wav_file(self, file_path: str, audio_data: np.ndarray, sample_rate: int) -> None:
        """Write numpy array to WAV file"""
        try:
            # Convert to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Write WAV file
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
                
        except Exception as e:
            logger.error(f"Error writing WAV file: {e}")
            raise
    
    def _parse_whisper_output(self, output: str) -> List[Dict[str, float]]:
        """Parse Whisper.cpp output to extract transcriptions and confidence"""
        transcriptions = []
        lines = output.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
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
                    transcriptions.append({
                        'text': text,
                        'confidence': 0.5
                    })
            else:
                # No confidence score, assume medium confidence
                transcriptions.append({
                    'text': line,
                    'confidence': 0.5
                })
        
        # Sort by confidence (highest first)
        transcriptions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        return transcriptions
    
    def transcribe_realtime(self, duration_seconds: float = 5.0) -> List[Dict[str, float]]:
        """
        Record and transcribe audio in real-time
        Args:
            duration_seconds: Duration to record
        Returns:
            Best transcription result
        """
        try:
            # Import ALSA I/O
            from .alsa_io import ALSAIO
            
            # Record audio
            alsa_io = ALSAIO()
            audio_data = alsa_io.record_audio(duration_seconds, self.sample_rate)
            
            if audio_data is None or len(audio_data) == 0:
                logger.error("Failed to record audio")
                return []
            
            # Transcribe
            transcriptions = self.transcribe_audio(audio_data, self.sample_rate)
            
            # Return best transcription
            if transcriptions:
                return [transcriptions[0]]  # Return only the best result
            
            return []
            
        except Exception as e:
            logger.error(f"Error in real-time transcription: {e}")
            return []
    
    def get_model_info(self) -> Dict[str, str]:
        """Get information about the loaded model"""
        return {
            'model_path': self.model_path,
            'model_name': os.path.basename(self.model_path),
            'whisper_binary': self.whisper_binary,
            'sample_rate': str(self.sample_rate),
            'gpu_available': str(self._check_gpu_available())
        }

class WhisperASRManager:
    """Manager for Whisper ASR with error handling and UI integration"""
    
    def __init__(self):
        self.asr = None
        self.is_recording = False
        self.recording_thread = None
        
    def initialize(self) -> bool:
        """Initialize ASR system"""
        try:
            self.asr = WhisperCppASR()
            logger.info("Whisper ASR initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Whisper ASR: {e}")
            return False
    
    def start_recording(self, duration_seconds: float = 5.0) -> None:
        """Start recording in background thread"""
        if self.is_recording:
            return
        
        self.is_recording = True
        
        def record_and_transcribe():
            try:
                if self.asr:
                    result = self.asr.transcribe_realtime(duration_seconds)
                    if result:
                        logger.info(f"Transcription result: {result[0]['text']} (confidence: {result[0]['confidence']:.2f})")
                    else:
                        logger.warning("No transcription result")
                else:
                    logger.error("ASR not initialized")
            except Exception as e:
                logger.error(f"Recording error: {e}")
            finally:
                self.is_recording = False
        
        self.recording_thread = threading.Thread(target=record_and_transcribe, daemon=True)
        self.recording_thread.start()
    
    def stop_recording(self) -> None:
        """Stop recording"""
        self.is_recording = False
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
    
    def transcribe_audio_data(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict[str, float]]:
        """Transcribe audio data"""
        if not self.asr:
            logger.error("ASR not initialized")
            return []
        
        return self.asr.transcribe_audio(audio_data, sample_rate)
    
    def get_status(self) -> Dict[str, Any]:
        """Get ASR status"""
        return {
            'initialized': self.asr is not None,
            'recording': self.is_recording,
            'model_info': self.asr.get_model_info() if self.asr else None
        }

def main():
    """Main function for testing"""
    asr_manager = WhisperASRManager()
    
    if not asr_manager.initialize():
        print("Failed to initialize ASR")
        return
    
    print("Whisper ASR Test")
    print("=" * 20)
    
    # Show model info
    status = asr_manager.get_status()
    if status['model_info']:
        print(f"Model: {status['model_info']['model_name']}")
        print(f"GPU Available: {status['model_info']['gpu_available']}")
    
    # Test real-time transcription
    print("\nStarting 5-second recording...")
    asr_manager.start_recording(5.0)
    
    # Wait for completion
    while asr_manager.is_recording:
        time.sleep(0.1)
    
    print("Recording completed")

if __name__ == "__main__":
    main()
