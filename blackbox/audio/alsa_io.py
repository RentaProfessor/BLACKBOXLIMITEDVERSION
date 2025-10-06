"""
ALSA-only audio I/O with device selection by name
Enforces 16 kHz/16-bit mono capture and 22.05 kHz/16-bit playback
"""

import os
import wave
import tempfile
import subprocess
import logging
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

class ALSAIO:
    """ALSA-only audio input/output with device selection by name"""
    
    def __init__(self, config_path: str = "/mnt/nvme/blackbox/config/audio.json"):
        self.config_path = config_path
        self.input_device = None
        self.output_device = None
        self.load_device_config()
    
    def load_device_config(self) -> None:
        """Load device configuration from JSON file"""
        try:
            import json
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                # Get default devices
                input_devices = config.get('input', [])
                output_devices = config.get('output', [])
                
                # Prefer USB devices
                for device in input_devices:
                    if 'usb' in device['name'].lower():
                        self.input_device = device
                        break
                
                for device in output_devices:
                    if 'usb' in device['name'].lower():
                        self.output_device = device
                        break
                
                # Fallback to first available device
                if not self.input_device and input_devices:
                    self.input_device = input_devices[0]
                
                if not self.output_device and output_devices:
                    self.output_device = output_devices[0]
                
                logger.info(f"Loaded audio devices: input={self.input_device['name'] if self.input_device else 'None'}, output={self.output_device['name'] if self.output_device else 'None'}")
                
        except Exception as e:
            logger.error(f"Failed to load audio device config: {e}")
    
    def set_input_device(self, device_name: str) -> bool:
        """Set input device by name"""
        try:
            import json
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                input_devices = config.get('input', [])
                for device in input_devices:
                    if device_name.lower() in device['name'].lower():
                        self.input_device = device
                        logger.info(f"Set input device to: {device['name']}")
                        return True
            
            logger.error(f"Input device '{device_name}' not found")
            return False
            
        except Exception as e:
            logger.error(f"Error setting input device: {e}")
            return False
    
    def set_output_device(self, device_name: str) -> bool:
        """Set output device by name"""
        try:
            import json
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                output_devices = config.get('output', [])
                for device in output_devices:
                    if device_name.lower() in device['name'].lower():
                        self.output_device = device
                        logger.info(f"Set output device to: {device['name']}")
                        return True
            
            logger.error(f"Output device '{device_name}' not found")
            return False
            
        except Exception as e:
            logger.error(f"Error setting output device: {e}")
            return False
    
    def record_audio(self, duration_seconds: float, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        Record audio using ALSA
        Args:
            duration_seconds: Duration to record
            sample_rate: Sample rate (default 16000 Hz)
        Returns:
            Audio data as numpy array or None if failed
        """
        if not self.input_device:
            logger.error("No input device configured")
            return None
        
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Record using arecord
            cmd = [
                'arecord',
                '-D', self.input_device['hw_id'],
                '-f', 'S16_LE',  # 16-bit signed little-endian
                '-r', str(sample_rate),
                '-c', '1',  # Mono
                '-d', str(int(duration_seconds))
            ]
            
            # Record to temporary file
            result = subprocess.run(
                cmd + [temp_path],
                capture_output=True,
                timeout=duration_seconds + 5
            )
            
            if result.returncode != 0:
                logger.error(f"arecord failed: {result.stderr.decode()}")
                return None
            
            # Read WAV file
            audio_data = self._read_wav_file(temp_path, sample_rate)
            
            # Clean up
            os.unlink(temp_path)
            
            return audio_data
            
        except subprocess.TimeoutExpired:
            logger.error("Audio recording timeout")
            return None
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            return None
    
    def play_audio(self, audio_data: np.ndarray, sample_rate: int = 22050) -> bool:
        """
        Play audio using ALSA
        Args:
            audio_data: Audio data as numpy array
            sample_rate: Sample rate (default 22050 Hz)
        Returns:
            True if successful, False otherwise
        """
        if not self.output_device:
            logger.error("No output device configured")
            return False
        
        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Write WAV file
            self._write_wav_file(temp_path, audio_data, sample_rate)
            
            # Play using aplay
            cmd = [
                'aplay',
                '-D', self.output_device['hw_id'],
                '-f', 'S16_LE',  # 16-bit signed little-endian
                '-r', str(sample_rate),
                '-c', '2' if len(audio_data.shape) > 1 and audio_data.shape[1] > 1 else '1'  # Stereo or mono
            ]
            
            result = subprocess.run(
                cmd + [temp_path],
                capture_output=True,
                timeout=30
            )
            
            # Clean up
            os.unlink(temp_path)
            
            if result.returncode != 0:
                logger.error(f"aplay failed: {result.stderr.decode()}")
                return False
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("Audio playback timeout")
            return False
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
            return False
    
    def _read_wav_file(self, file_path: str, target_sample_rate: int) -> Optional[np.ndarray]:
        """Read WAV file and convert to target sample rate"""
        try:
            with wave.open(file_path, 'rb') as wav_file:
                # Get WAV parameters
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                frames = wav_file.getnframes()
                
                # Read audio data
                raw_data = wav_file.readframes(frames)
                
                # Convert to numpy array
                if sample_width == 2:
                    audio_data = np.frombuffer(raw_data, dtype=np.int16)
                elif sample_width == 4:
                    audio_data = np.frombuffer(raw_data, dtype=np.int32)
                else:
                    logger.error(f"Unsupported sample width: {sample_width}")
                    return None
                
                # Convert to float32 and normalize
                audio_data = audio_data.astype(np.float32) / 32767.0
                
                # Reshape for multi-channel
                if channels > 1:
                    audio_data = audio_data.reshape(-1, channels)
                
                # Resample if needed
                if sample_rate != target_sample_rate:
                    audio_data = self._resample_audio(audio_data, sample_rate, target_sample_rate)
                
                return audio_data
                
        except Exception as e:
            logger.error(f"Error reading WAV file: {e}")
            return None
    
    def _write_wav_file(self, file_path: str, audio_data: np.ndarray, sample_rate: int) -> None:
        """Write numpy array to WAV file"""
        try:
            # Ensure audio data is in the right format
            if len(audio_data.shape) == 1:
                channels = 1
            else:
                channels = audio_data.shape[1]
            
            # Convert to int16
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            # Write WAV file
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
                
        except Exception as e:
            logger.error(f"Error writing WAV file: {e}")
            raise
    
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
    
    def test_audio_system(self) -> Dict[str, bool]:
        """Test audio input and output"""
        results = {
            'input': False,
            'output': False
        }
        
        # Test input
        if self.input_device:
            logger.info("Testing audio input...")
            audio_data = self.record_audio(1.0)  # Record 1 second
            if audio_data is not None and len(audio_data) > 0:
                results['input'] = True
                logger.info("Audio input test passed")
            else:
                logger.error("Audio input test failed")
        
        # Test output
        if self.output_device:
            logger.info("Testing audio output...")
            # Generate a test tone
            sample_rate = 22050
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration))
            test_tone = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone
            
            if self.play_audio(test_tone, sample_rate):
                results['output'] = True
                logger.info("Audio output test passed")
            else:
                logger.error("Audio output test failed")
        
        return results
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get information about configured devices"""
        return {
            'input': {
                'name': self.input_device['name'] if self.input_device else None,
                'hw_id': self.input_device['hw_id'] if self.input_device else None
            },
            'output': {
                'name': self.output_device['name'] if self.output_device else None,
                'hw_id': self.output_device['hw_id'] if self.output_device else None
            }
        }

def main():
    """Main function for testing"""
    alsa_io = ALSAIO()
    
    print("ALSA Audio I/O Test")
    print("=" * 30)
    
    # Show device info
    device_info = alsa_io.get_device_info()
    print(f"Input Device: {device_info['input']['name']} ({device_info['input']['hw_id']})")
    print(f"Output Device: {device_info['output']['name']} ({device_info['output']['hw_id']})")
    
    # Test audio system
    print("\nTesting audio system...")
    results = alsa_io.test_audio_system()
    
    print(f"Input Test: {'PASS' if results['input'] else 'FAIL'}")
    print(f"Output Test: {'PASS' if results['output'] else 'FAIL'}")

if __name__ == "__main__":
    main()
