"""
Main UI for BLACK BOX - Touch-friendly interface for elderly users
Fullscreen PySide6 application with high contrast design
"""

import sys
import os
import time
import threading
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QTextEdit, QLineEdit, QMessageBox,
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QPropertyAnimation, QEasingCurve,
    QRect, QSize
)
from PySide6.QtGui import (
    QFont, QPalette, QColor, QPixmap, QPainter, QBrush, QPen,
    QKeySequence, QShortcut
)

# Import our modules
from ..audio.asr import WhisperASR, AudioProcessor
from ..audio.tts import AudioManager
from ..nlp.resolve import IntentResolver
from ..vault.db import VaultDatabase, VaultEntry

logger = logging.getLogger(__name__)

class VirtualKeyboard(QWidget):
    """Virtual keyboard for passphrase entry"""
    
    key_pressed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup virtual keyboard UI"""
        layout = QVBoxLayout()
        
        # Keyboard rows
        rows = [
            "1234567890",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm"
        ]
        
        for row in rows:
            row_layout = QHBoxLayout()
            for char in row:
                btn = QPushButton(char.upper())
                btn.setFixedSize(60, 60)
                btn.setFont(QFont("Arial", 24, QFont.Bold))
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #333333;
                        color: #FFFFFF;
                        border: 2px solid #666666;
                        border-radius: 8px;
                    }
                    QPushButton:pressed {
                        background-color: #555555;
                    }
                """)
                btn.clicked.connect(lambda checked, c=char: self.key_pressed.emit(c))
                row_layout.addWidget(btn)
            layout.addLayout(row_layout)
        
        # Special keys
        special_layout = QHBoxLayout()
        
        space_btn = QPushButton("SPACE")
        space_btn.setFixedSize(200, 60)
        space_btn.setFont(QFont("Arial", 18, QFont.Bold))
        space_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 2px solid #666666;
                border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
        """)
        space_btn.clicked.connect(lambda: self.key_pressed.emit(" "))
        special_layout.addWidget(space_btn)
        
        backspace_btn = QPushButton("⌫")
        backspace_btn.setFixedSize(100, 60)
        backspace_btn.setFont(QFont("Arial", 24, QFont.Bold))
        backspace_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: #FFFFFF;
                border: 2px solid #FF0000;
                border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #AA0000;
            }
        """)
        backspace_btn.clicked.connect(lambda: self.key_pressed.emit("backspace"))
        special_layout.addWidget(backspace_btn)
        
        layout.addLayout(special_layout)
        self.setLayout(layout)

class StatusBar(QFrame):
    """Status bar with color-coded indicators"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup status bar UI"""
        self.setFixedHeight(80)
        self.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 2px solid #333333;
                border-radius: 8px;
            }
        """)
        
        layout = QHBoxLayout()
        
        # Status indicator
        self.status_label = QLabel("READY")
        self.status_label.setFont(QFont("Arial", 20, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.status_label)
        
        # Time display
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.time_label)
        
        # Update time
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
        
        self.setLayout(layout)
    
    def update_time(self):
        """Update time display"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.setText(current_time)
    
    def set_status(self, status: str, color: str = "#FFFFFF"):
        """Set status with color"""
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {color};")

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.vault = VaultDatabase()
        self.audio_manager = AudioManager()
        self.asr = WhisperASR()
        self.intent_resolver = IntentResolver()
        
        # UI state
        self.current_state = "main"  # main, recording, saving, retrieving, locked
        self.recording_thread = None
        self.reveal_timer = None
        self.reveal_countdown = 0
        
        # Setup UI
        self.setup_ui()
        self.setup_shortcuts()
        
        # Check if vault needs initialization
        self.check_vault_status()
    
    def setup_ui(self):
        """Setup main UI"""
        # Set window properties
        self.setWindowTitle("BLACK BOX")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Set fullscreen
        self.showFullScreen()
        
        # Set background color
        self.setStyleSheet("""
            QMainWindow {
                background-color: #000000;
            }
        """)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Status bar
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)
        
        # Main content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_widget.setLayout(self.content_layout)
        main_layout.addWidget(self.content_widget)
        
        central_widget.setLayout(main_layout)
        
        # Setup different views
        self.setup_main_view()
        self.setup_recording_view()
        self.setup_locked_view()
        self.setup_passphrase_view()
    
    def setup_main_view(self):
        """Setup main menu view"""
        self.main_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(30)
        
        # Title
        title = QLabel("BLACK BOX")
        title.setFont(QFont("Arial", 48, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FFFF00; margin: 20px;")
        layout.addWidget(title)
        
        # Button grid
        button_layout = QGridLayout()
        button_layout.setSpacing(20)
        
        # Record button
        self.record_btn = QPushButton("RECORD")
        self.record_btn.setFixedSize(200, 200)
        self.record_btn.setFont(QFont("Arial", 24, QFont.Bold))
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066CC;
                color: #FFFFFF;
                border: 4px solid #0088FF;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
        """)
        self.record_btn.clicked.connect(self.start_recording)
        button_layout.addWidget(self.record_btn, 0, 0)
        
        # Save button
        self.save_btn = QPushButton("SAVE")
        self.save_btn.setFixedSize(200, 200)
        self.save_btn.setFont(QFont("Arial", 24, QFont.Bold))
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #00AA00;
                color: #FFFFFF;
                border: 4px solid #00CC00;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #008800;
            }
        """)
        self.save_btn.clicked.connect(self.save_password)
        button_layout.addWidget(self.save_btn, 0, 1)
        
        # Retrieve button
        self.retrieve_btn = QPushButton("RETRIEVE")
        self.retrieve_btn.setFixedSize(200, 200)
        self.retrieve_btn.setFont(QFont("Arial", 24, QFont.Bold))
        self.retrieve_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC6600;
                color: #FFFFFF;
                border: 4px solid #FF8800;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #AA4400;
            }
        """)
        self.retrieve_btn.clicked.connect(self.retrieve_password)
        button_layout.addWidget(self.retrieve_btn, 1, 0)
        
        # Cancel button
        self.cancel_btn = QPushButton("CANCEL")
        self.cancel_btn.setFixedSize(200, 200)
        self.cancel_btn.setFont(QFont("Arial", 24, QFont.Bold))
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: #FFFFFF;
                border: 4px solid #FF0000;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #AA0000;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_btn, 1, 1)
        
        layout.addLayout(button_layout)
        
        # Reveal button (initially hidden)
        self.reveal_btn = QPushButton("REVEAL (10s)")
        self.reveal_btn.setFixedSize(300, 100)
        self.reveal_btn.setFont(QFont("Arial", 20, QFont.Bold))
        self.reveal_btn.setStyleSheet("""
            QPushButton {
                background-color: #6600CC;
                color: #FFFFFF;
                border: 4px solid #8800FF;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #4400AA;
            }
        """)
        self.reveal_btn.clicked.connect(self.reveal_password)
        self.reveal_btn.hide()
        layout.addWidget(self.reveal_btn)
        
        # Display area
        self.display_label = QLabel("")
        self.display_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: #333333;
                border: 2px solid #666666;
                border-radius: 10px;
                padding: 20px;
                min-height: 100px;
            }
        """)
        self.display_label.setWordWrap(True)
        layout.addWidget(self.display_label)
        
        self.main_widget.setLayout(layout)
    
    def setup_recording_view(self):
        """Setup recording view"""
        self.recording_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(30)
        
        # Recording indicator
        self.recording_label = QLabel("RECORDING...")
        self.recording_label.setFont(QFont("Arial", 36, QFont.Bold))
        self.recording_label.setAlignment(Qt.AlignCenter)
        self.recording_label.setStyleSheet("color: #FF0000;")
        layout.addWidget(self.recording_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(40)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #666666;
                border-radius: 8px;
                text-align: center;
                font-size: 18px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #FF0000;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Stop recording button
        self.stop_btn = QPushButton("STOP RECORDING")
        self.stop_btn.setFixedSize(300, 150)
        self.stop_btn.setFont(QFont("Arial", 24, QFont.Bold))
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: #FFFFFF;
                border: 4px solid #FF0000;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #AA0000;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_recording)
        layout.addWidget(self.stop_btn)
        
        self.recording_widget.setLayout(layout)
    
    def setup_locked_view(self):
        """Setup locked view"""
        self.locked_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(30)
        
        # Locked indicator
        locked_label = QLabel("VAULT LOCKED")
        locked_label.setFont(QFont("Arial", 36, QFont.Bold))
        locked_label.setAlignment(Qt.AlignCenter)
        locked_label.setStyleSheet("color: #FF0000;")
        layout.addWidget(locked_label)
        
        # Unlock button
        unlock_btn = QPushButton("UNLOCK VAULT")
        unlock_btn.setFixedSize(300, 150)
        unlock_btn.setFont(QFont("Arial", 24, QFont.Bold))
        unlock_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066CC;
                color: #FFFFFF;
                border: 4px solid #0088FF;
                border-radius: 20px;
            }
            QPushButton:pressed {
                background-color: #004499;
            }
        """)
        unlock_btn.clicked.connect(self.show_passphrase_view)
        layout.addWidget(unlock_btn)
        
        self.locked_widget.setLayout(layout)
    
    def setup_passphrase_view(self):
        """Setup passphrase entry view"""
        self.passphrase_widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(30)
        
        # Title
        title = QLabel("ENTER PASSPHRASE")
        title.setFont(QFont("Arial", 32, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #FFFF00;")
        layout.addWidget(title)
        
        # Passphrase input
        self.passphrase_input = QLineEdit()
        self.passphrase_input.setFixedHeight(80)
        self.passphrase_input.setFont(QFont("Arial", 24, QFont.Bold))
        self.passphrase_input.setEchoMode(QLineEdit.Password)
        self.passphrase_input.setStyleSheet("""
            QLineEdit {
                background-color: #333333;
                color: #FFFFFF;
                border: 3px solid #666666;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.passphrase_input)
        
        # Virtual keyboard
        self.virtual_keyboard = VirtualKeyboard()
        self.virtual_keyboard.key_pressed.connect(self.handle_keyboard_input)
        layout.addWidget(self.virtual_keyboard)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        unlock_btn = QPushButton("UNLOCK")
        unlock_btn.setFixedSize(200, 100)
        unlock_btn.setFont(QFont("Arial", 20, QFont.Bold))
        unlock_btn.setStyleSheet("""
            QPushButton {
                background-color: #00AA00;
                color: #FFFFFF;
                border: 4px solid #00CC00;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #008800;
            }
        """)
        unlock_btn.clicked.connect(self.unlock_vault)
        button_layout.addWidget(unlock_btn)
        
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedSize(200, 100)
        cancel_btn.setFont(QFont("Arial", 20, QFont.Bold))
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #CC0000;
                color: #FFFFFF;
                border: 4px solid #FF0000;
                border-radius: 15px;
            }
            QPushButton:pressed {
                background-color: #AA0000;
            }
        """)
        cancel_btn.clicked.connect(self.show_main_view)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.passphrase_widget.setLayout(layout)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Escape to cancel
        QShortcut(QKeySequence("Escape"), self, self.cancel_operation)
        
        # Space to start recording
        QShortcut(QKeySequence("Space"), self, self.start_recording)
    
    def check_vault_status(self):
        """Check if vault needs initialization or is locked"""
        if not os.path.exists(self.vault.db_path):
            # First time setup
            self.show_passphrase_view()
        elif not self.vault.is_unlocked:
            # Vault is locked
            self.show_locked_view()
        else:
            # Vault is unlocked
            self.show_main_view()
    
    def show_main_view(self):
        """Show main menu view"""
        self.current_state = "main"
        self.clear_content()
        self.content_layout.addWidget(self.main_widget)
        self.status_bar.set_status("READY", "#FFFFFF")
    
    def show_recording_view(self):
        """Show recording view"""
        self.current_state = "recording"
        self.clear_content()
        self.content_layout.addWidget(self.recording_widget)
        self.status_bar.set_status("RECORDING", "#FF0000")
    
    def show_locked_view(self):
        """Show locked view"""
        self.current_state = "locked"
        self.clear_content()
        self.content_layout.addWidget(self.locked_widget)
        self.status_bar.set_status("LOCKED", "#FF0000")
    
    def show_passphrase_view(self):
        """Show passphrase entry view"""
        self.current_state = "passphrase"
        self.clear_content()
        self.content_layout.addWidget(self.passphrase_widget)
        self.status_bar.set_status("ENTER PASSPHRASE", "#FFFF00")
        self.passphrase_input.setFocus()
    
    def clear_content(self):
        """Clear content area"""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().hide()
    
    def handle_keyboard_input(self, key: str):
        """Handle virtual keyboard input"""
        if key == "backspace":
            current_text = self.passphrase_input.text()
            self.passphrase_input.setText(current_text[:-1])
        else:
            current_text = self.passphrase_input.text()
            self.passphrase_input.setText(current_text + key)
    
    def unlock_vault(self):
        """Unlock vault with passphrase"""
        passphrase = self.passphrase_input.text()
        if not passphrase:
            self.audio_manager.error()
            return
        
        if self.vault.unlock_vault(passphrase):
            self.audio_manager.speak("Vault unlocked successfully")
            self.show_main_view()
        else:
            self.audio_manager.error()
            self.passphrase_input.clear()
    
    def start_recording(self):
        """Start voice recording"""
        if self.current_state != "main":
            return
        
        self.show_recording_view()
        self.audio_manager.recording_start()
        
        # Start recording in background thread
        self.recording_thread = threading.Thread(target=self._record_audio, daemon=True)
        self.recording_thread.start()
    
    def _record_audio(self):
        """Record audio in background thread"""
        try:
            # Record for up to 10 seconds
            audio_data = self.asr.transcribe_realtime(duration_seconds=10.0)
            
            if audio_data:
                # Process transcription
                self.process_transcription(audio_data[0]['text'])
            else:
                self.audio_manager.error()
                self.show_main_view()
                
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self.audio_manager.error()
            self.show_main_view()
    
    def stop_recording(self):
        """Stop voice recording"""
        if self.recording_thread:
            # Signal to stop recording
            self.asr.stop_recording()
            self.recording_thread.join(timeout=2.0)
        
        self.audio_manager.recording_stop()
        self.show_main_view()
    
    def process_transcription(self, text: str):
        """Process transcribed text"""
        if not text:
            self.audio_manager.error()
            return
        
        # Display transcribed text
        self.display_label.setText(f"Transcribed: {text}")
        
        # Resolve intent based on current state
        intent_result = self.intent_resolver.resolve_intent(text, self.current_state)
        
        if intent_result['intent'] == 'save':
            self.handle_save_intent(intent_result)
        elif intent_result['intent'] == 'retrieve':
            self.handle_retrieve_intent(intent_result)
        else:
            self.audio_manager.error()
    
    def handle_save_intent(self, intent_result: Dict[str, Any]):
        """Handle save password intent"""
        entities = intent_result['entities']
        site = entities.get('site')
        password = entities.get('password', '')
        
        if site and password:
            # Save to vault
            if self.vault.save_password(site, password):
                self.audio_manager.success()
                self.display_label.setText(f"Saved password for {site}")
            else:
                self.audio_manager.error()
        else:
            self.audio_manager.error()
    
    def handle_retrieve_intent(self, intent_result: Dict[str, Any]):
        """Handle retrieve password intent"""
        entities = intent_result['entities']
        site = entities.get('site')
        
        if site:
            # Retrieve from vault
            entry = self.vault.retrieve_password(site)
            if entry:
                self.audio_manager.speak("Password retrieved")
                self.display_label.setText(f"Retrieved password for {site}")
                self.reveal_btn.show()
            else:
                self.audio_manager.error()
                self.display_label.setText(f"No password found for {site}")
        else:
            self.audio_manager.error()
    
    def reveal_password(self):
        """Reveal password for 10 seconds"""
        # This would show the actual password
        # For security, we'll just show a placeholder
        self.display_label.setText("Password: ********")
        
        # Start countdown
        self.reveal_countdown = 10
        self.reveal_timer = QTimer()
        self.reveal_timer.timeout.connect(self.update_reveal_countdown)
        self.reveal_timer.start(1000)
        
        # Update button text
        self.reveal_btn.setText(f"REVEAL ({self.reveal_countdown}s)")
    
    def update_reveal_countdown(self):
        """Update reveal countdown"""
        self.reveal_countdown -= 1
        
        if self.reveal_countdown <= 0:
            # Hide password
            self.display_label.setText("Password hidden")
            self.reveal_btn.hide()
            self.reveal_timer.stop()
        else:
            # Update button text
            self.reveal_btn.setText(f"REVEAL ({self.reveal_countdown}s)")
    
    def save_password(self):
        """Save password mode"""
        self.current_state = "save"
        self.audio_manager.speak("Please speak the site name and password")
        self.display_label.setText("Speak: 'Save password for [site] [password]'")
    
    def retrieve_password(self):
        """Retrieve password mode"""
        self.current_state = "retrieve"
        self.audio_manager.speak("Please speak the site name")
        self.display_label.setText("Speak: 'Get password for [site]'")
    
    def cancel_operation(self):
        """Cancel current operation"""
        if self.current_state == "recording":
            self.stop_recording()
        elif self.current_state in ["save", "retrieve"]:
            self.current_state = "main"
            self.display_label.setText("")
            self.reveal_btn.hide()
        elif self.current_state == "passphrase":
            self.show_main_view()
    
    def closeEvent(self, event):
        """Handle application close"""
        # Clean up resources
        if self.vault:
            self.vault.close()
        
        if self.audio_manager:
            self.audio_manager.shutdown()
        
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("BLACK BOX")
    app.setApplicationVersion("1.0.0")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
