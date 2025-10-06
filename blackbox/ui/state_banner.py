"""
State banner for elderly users with large fonts and color-coded indicators
Big state banner (RED "RECORDING", GREEN "SAVED"), large fonts ≥36pt
"""

import logging
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QPalette, QColor

logger = logging.getLogger(__name__)

class StateBanner(QWidget):
    """Large state banner with color-coded indicators"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.current_state = "ready"
        self.countdown_timer = None
        self.countdown_value = 0
    
    def setup_ui(self):
        """Setup state banner UI"""
        self.setFixedHeight(120)
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border: 3px solid #333333;
                border-radius: 15px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Main state label
        self.state_label = QLabel("READY")
        self.state_label.setFont(QFont("Arial", 48, QFont.Bold))
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self.state_label)
        
        # Subtitle label
        self.subtitle_label = QLabel("")
        self.subtitle_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(self.subtitle_label)
        
        self.setLayout(layout)
    
    def set_state(self, state: str, subtitle: str = ""):
        """Set banner state with color coding"""
        self.current_state = state
        
        # Define state colors and messages
        state_config = {
            "ready": {
                "color": "#FFFFFF",
                "message": "READY",
                "subtitle": "Touch a button to begin"
            },
            "recording": {
                "color": "#FF0000",
                "message": "RECORDING",
                "subtitle": "Please speak now"
            },
            "processing": {
                "color": "#FF8800",
                "message": "PROCESSING",
                "subtitle": "Please wait..."
            },
            "saved": {
                "color": "#00FF00",
                "message": "SAVED",
                "subtitle": "Password saved successfully"
            },
            "retrieved": {
                "color": "#00AA00",
                "message": "RETRIEVED",
                "subtitle": "Password retrieved"
            },
            "error": {
                "color": "#FF0000",
                "message": "ERROR",
                "subtitle": "Please try again"
            },
            "locked": {
                "color": "#FF0000",
                "message": "LOCKED",
                "subtitle": "Vault is locked"
            },
            "unlocking": {
                "color": "#FFFF00",
                "message": "UNLOCKING",
                "subtitle": "Enter passphrase"
            },
            "confirm": {
                "color": "#FF8800",
                "message": "CONFIRM",
                "subtitle": "Is this correct?"
            }
        }
        
        config = state_config.get(state, state_config["ready"])
        
        # Update labels
        self.state_label.setText(config["message"])
        self.state_label.setStyleSheet(f"color: {config['color']};")
        
        if subtitle:
            self.subtitle_label.setText(subtitle)
        else:
            self.subtitle_label.setText(config["subtitle"])
        
        # Add pulsing animation for active states
        if state in ["recording", "processing"]:
            self._start_pulsing_animation()
        else:
            self._stop_pulsing_animation()
        
        logger.info(f"State banner changed to: {state}")
    
    def start_countdown(self, seconds: int, message: str = "REVEAL"):
        """Start countdown with message"""
        self.countdown_value = seconds
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)  # Update every second
        
        self.set_state("countdown", f"{message} ({self.countdown_value}s)")
    
    def _update_countdown(self):
        """Update countdown display"""
        self.countdown_value -= 1
        
        if self.countdown_value <= 0:
            self.countdown_timer.stop()
            self.set_state("ready", "Countdown finished")
        else:
            self.set_state("countdown", f"REVEAL ({self.countdown_value}s)")
    
    def _start_pulsing_animation(self):
        """Start pulsing animation for active states"""
        self.pulse_animation = QPropertyAnimation(self.state_label, b"opacity")
        self.pulse_animation.setDuration(1000)
        self.pulse_animation.setStartValue(1.0)
        self.pulse_animation.setEndValue(0.5)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.pulse_animation.setLoopCount(-1)  # Infinite loop
        self.pulse_animation.start()
    
    def _stop_pulsing_animation(self):
        """Stop pulsing animation"""
        if hasattr(self, 'pulse_animation'):
            self.pulse_animation.stop()
            self.state_label.setStyleSheet(self.state_label.styleSheet().replace("opacity: 0.5;", ""))
    
    def show_confirmation(self, message: str, callback=None):
        """Show confirmation dialog"""
        self.set_state("confirm", message)
        self.confirmation_callback = callback
    
    def hide_confirmation(self):
        """Hide confirmation dialog"""
        self.set_state("ready")
        if hasattr(self, 'confirmation_callback'):
            delattr(self, 'confirmation_callback')

class ConfirmationDialog(QWidget):
    """Large confirmation dialog for elderly users"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.callback = None
    
    def setup_ui(self):
        """Setup confirmation dialog UI"""
        self.setFixedSize(400, 300)
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border: 4px solid #FF8800;
                border-radius: 20px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Message label
        self.message_label = QLabel("")
        self.message_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("color: #FFFFFF;")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)
        
        # Button layout
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        
        # Yes button
        self.yes_button = QLabel("✓ YES")
        self.yes_button.setFixedSize(200, 80)
        self.yes_button.setFont(QFont("Arial", 28, QFont.Bold))
        self.yes_button.setAlignment(Qt.AlignCenter)
        self.yes_button.setStyleSheet("""
            QLabel {
                background-color: #00AA00;
                color: #FFFFFF;
                border: 3px solid #00CC00;
                border-radius: 15px;
            }
            QLabel:hover {
                background-color: #008800;
            }
        """)
        self.yes_button.mousePressEvent = self._on_yes_clicked
        button_layout.addWidget(self.yes_button)
        
        # No button
        self.no_button = QLabel("✕ NO")
        self.no_button.setFixedSize(200, 80)
        self.no_button.setFont(QFont("Arial", 28, QFont.Bold))
        self.no_button.setAlignment(Qt.AlignCenter)
        self.no_button.setStyleSheet("""
            QLabel {
                background-color: #CC0000;
                color: #FFFFFF;
                border: 3px solid #FF0000;
                border-radius: 15px;
            }
            QLabel:hover {
                background-color: #AA0000;
            }
        """)
        self.no_button.mousePressEvent = self._on_no_clicked
        button_layout.addWidget(self.no_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def show_confirmation(self, message: str, callback):
        """Show confirmation dialog"""
        self.message_label.setText(message)
        self.callback = callback
        self.show()
    
    def _on_yes_clicked(self, event):
        """Handle yes button click"""
        if self.callback:
            self.callback(True)
        self.hide()
    
    def _on_no_clicked(self, event):
        """Handle no button click"""
        if self.callback:
            self.callback(False)
        self.hide()

def main():
    """Test the state banner"""
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("State Banner Test")
    window.setFixedSize(800, 600)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout()
    
    # State banner
    banner = StateBanner()
    layout.addWidget(banner)
    
    # Test buttons
    test_button = QPushButton("Test Recording")
    test_button.clicked.connect(lambda: banner.set_state("recording"))
    layout.addWidget(test_button)
    
    test_button2 = QPushButton("Test Saved")
    test_button2.clicked.connect(lambda: banner.set_state("saved"))
    layout.addWidget(test_button2)
    
    test_button3 = QPushButton("Test Countdown")
    test_button3.clicked.connect(lambda: banner.start_countdown(10, "REVEAL"))
    layout.addWidget(test_button3)
    
    central_widget.setLayout(layout)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
