"""
Audio feedback system for elderly users
Optional beeps (1× start, 2× stop, 3× success) via short WAVs in assets/beeps/
"""

import os
import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl

logger = logging.getLogger(__name__)

class AudioFeedback(QObject):
    """Audio feedback system using WAV files"""
    
    feedback_completed = Signal()
    
    def __init__(self, assets_dir: str = "/mnt/nvme/blackbox/assets/beeps"):
        super().__init__()
        self.assets_dir = assets_dir
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Set volume
        self.audio_output.setVolume(0.8)
        
        # Connect signals
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        
        # Check if beep files exist
        self._check_beep_files()
    
    def _check_beep_files(self):
        """Check if beep files exist, create if missing"""
        beep_files = [
            "recording_start.wav",
            "recording_stop.wav", 
            "success.wav",
            "error.wav",
            "confirm.wav"
        ]
        
        for beep_file in beep_files:
            beep_path = os.path.join(self.assets_dir, beep_file)
            if not os.path.exists(beep_path):
                logger.warning(f"Beep file not found: {beep_path}")
                # Create a simple beep file
                self._create_simple_beep(beep_path, beep_file)
    
    def _create_simple_beep(self, file_path: str, beep_type: str):
        """Create a simple beep file if missing"""
        try:
            import numpy as np
            import wave
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Generate beep based on type
            if beep_type == "recording_start.wav":
                beep = self._generate_beep(800, 0.3)
            elif beep_type == "recording_stop.wav":
                beep = self._generate_beep(600, 0.2)
                beep = np.concatenate([beep, np.zeros(int(0.1 * 22050)), beep])
            elif beep_type == "success.wav":
                beep = self._generate_beep(1000, 0.15)
                beep = np.concatenate([beep, np.zeros(int(0.1 * 22050)), beep, np.zeros(int(0.1 * 22050)), beep])
            elif beep_type == "error.wav":
                beep = self._generate_beep(400, 0.5)
            elif beep_type == "confirm.wav":
                beep = self._generate_beep(700, 0.2)
                beep = np.concatenate([beep, np.zeros(int(0.1 * 22050)), beep])
            else:
                beep = self._generate_beep(800, 0.3)
            
            # Save as WAV file
            audio_int16 = (beep * 32767).astype(np.int16)
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                wav_file.writeframes(audio_int16.tobytes())
            
            logger.info(f"Created beep file: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to create beep file {file_path}: {e}")
    
    def _generate_beep(self, frequency: float, duration: float) -> np.ndarray:
        """Generate a beep tone"""
        import numpy as np
        sample_rate = 22050
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        beep = 0.3 * np.sin(2 * np.pi * frequency * t)
        
        # Apply fade in/out
        fade_samples = int(0.01 * sample_rate)
        beep[:fade_samples] *= np.linspace(0, 1, fade_samples)
        beep[-fade_samples:] *= np.linspace(1, 0, fade_samples)
        
        return beep.astype(np.float32)
    
    def _on_playback_state_changed(self, state):
        """Handle playback state changes"""
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self.feedback_completed.emit()
    
    def play_beep(self, beep_type: str) -> bool:
        """Play a beep sound"""
        beep_path = os.path.join(self.assets_dir, f"{beep_type}.wav")
        
        if not os.path.exists(beep_path):
            logger.error(f"Beep file not found: {beep_path}")
            return False
        
        try:
            self.player.setSource(QUrl.fromLocalFile(beep_path))
            self.player.play()
            return True
        except Exception as e:
            logger.error(f"Error playing beep {beep_type}: {e}")
            return False
    
    def recording_start(self):
        """Play recording start beep"""
        return self.play_beep("recording_start")
    
    def recording_stop(self):
        """Play recording stop beep"""
        return self.play_beep("recording_stop")
    
    def success(self):
        """Play success beep"""
        return self.play_beep("success")
    
    def error(self):
        """Play error beep"""
        return self.play_beep("error")
    
    def confirm(self):
        """Play confirm beep"""
        return self.play_beep("confirm")
    
    def set_volume(self, volume: float):
        """Set audio volume (0.0 to 1.0)"""
        self.audio_output.setVolume(volume)
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

class AudioFeedbackManager:
    """Manager for audio feedback with TTS integration"""
    
    def __init__(self, tts_manager=None):
        self.audio_feedback = AudioFeedback()
        self.tts_manager = tts_manager
        self.enabled = True
    
    def set_enabled(self, enabled: bool):
        """Enable or disable audio feedback"""
        self.enabled = enabled
    
    def recording_start(self):
        """Audio feedback for recording start"""
        if self.enabled:
            self.audio_feedback.recording_start()
            if self.tts_manager:
                self.tts_manager.speak("Recording started. Please speak now.")
    
    def recording_stop(self):
        """Audio feedback for recording stop"""
        if self.enabled:
            self.audio_feedback.recording_stop()
            if self.tts_manager:
                self.tts_manager.speak("Recording stopped.")
    
    def success(self):
        """Audio feedback for success"""
        if self.enabled:
            self.audio_feedback.success()
            if self.tts_manager:
                self.tts_manager.speak("Success.")
    
    def error(self):
        """Audio feedback for error"""
        if self.enabled:
            self.audio_feedback.error()
            if self.tts_manager:
                self.tts_manager.speak("Error. Please try again.")
    
    def confirm(self):
        """Audio feedback for confirmation"""
        if self.enabled:
            self.audio_feedback.confirm()
            if self.tts_manager:
                self.tts_manager.speak("Please confirm.")
    
    def speak_status(self, status: str):
        """Speak status message"""
        if self.enabled and self.tts_manager:
            status_messages = {
                'saved': "Password saved successfully.",
                'retrieved': "Password retrieved.",
                'locked': "Vault is locked.",
                'unlocked': "Vault unlocked.",
                'timeout': "Session timed out."
            }
            
            message = status_messages.get(status, status)
            self.tts_manager.speak(message)

def main():
    """Test audio feedback"""
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Audio Feedback Test")
    window.setFixedSize(400, 300)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout()
    
    # Audio feedback manager
    feedback_manager = AudioFeedbackManager()
    
    # Test buttons
    buttons = [
        ("Recording Start", feedback_manager.recording_start),
        ("Recording Stop", feedback_manager.recording_stop),
        ("Success", feedback_manager.success),
        ("Error", feedback_manager.error),
        ("Confirm", feedback_manager.confirm)
    ]
    
    for text, callback in buttons:
        button = QPushButton(text)
        button.clicked.connect(callback)
        layout.addWidget(button)
    
    central_widget.setLayout(layout)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
