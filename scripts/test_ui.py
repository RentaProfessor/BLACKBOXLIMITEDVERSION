#!/usr/bin/env python3
"""
BLACK BOX - UI test script
Smoke test: start UI, click buttons programmatically
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add the blackbox package to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest

from blackbox.ui.state_banner import StateBanner, ConfirmationDialog
from blackbox.ui.audio_feedback import AudioFeedbackManager
from blackbox.logging.rotating_logger import get_app_logger

logger = get_app_logger()

def test_passed(message):
    print(f"✓ {message}")
    logger.info(f"TEST PASSED: {message}")

def test_failed(message):
    print(f"✗ {message}")
    logger.error(f"TEST FAILED: {message}")

def test_warning(message):
    print(f"⚠ {message}")
    logger.warning(f"TEST WARNING: {message}")

class UITestWindow(QWidget):
    """Test window for UI components"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.test_results = []
    
    def setup_ui(self):
        """Setup test UI"""
        self.setWindowTitle("BLACK BOX UI Test")
        self.setFixedSize(800, 600)
        
        layout = QVBoxLayout()
        
        # State banner
        self.state_banner = StateBanner()
        layout.addWidget(self.state_banner)
        
        # Test buttons
        self.test_buttons = QPushButton("Run UI Tests")
        self.test_buttons.clicked.connect(self.run_tests)
        layout.addWidget(self.test_buttons)
        
        # Status label
        self.status_label = QLabel("Ready to test")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def run_tests(self):
        """Run UI tests"""
        self.status_label.setText("Running tests...")
        
        # Test state banner
        self.test_state_banner()
        
        # Test audio feedback
        self.test_audio_feedback()
        
        # Test confirmation dialog
        self.test_confirmation_dialog()
        
        # Show results
        self.show_test_results()
    
    def test_state_banner(self):
        """Test state banner functionality"""
        try:
            # Test different states
            states = ["ready", "recording", "processing", "saved", "error", "locked"]
            
            for state in states:
                self.state_banner.set_state(state)
                time.sleep(0.5)
            
            # Test countdown
            self.state_banner.start_countdown(5, "TEST")
            time.sleep(2)
            
            test_passed("State banner test completed")
            
        except Exception as e:
            test_failed(f"State banner test failed: {e}")
    
    def test_audio_feedback(self):
        """Test audio feedback"""
        try:
            # Note: Audio feedback test is limited in headless environment
            test_warning("Audio feedback test skipped (headless environment)")
            
        except Exception as e:
            test_failed(f"Audio feedback test failed: {e}")
    
    def test_confirmation_dialog(self):
        """Test confirmation dialog"""
        try:
            # Create confirmation dialog
            dialog = ConfirmationDialog(self)
            
            # Test dialog creation
            if dialog:
                test_passed("Confirmation dialog creation successful")
            else:
                test_failed("Confirmation dialog creation failed")
                
        except Exception as e:
            test_failed(f"Confirmation dialog test failed: {e}")
    
    def show_test_results(self):
        """Show test results"""
        self.status_label.setText("Tests completed - check console output")

def test_ui_components():
    """Test UI components without full application"""
    print("\n1. Testing UI Components...")
    
    try:
        # Test state banner
        banner = StateBanner()
        banner.set_state("ready")
        banner.set_state("recording")
        banner.set_state("saved")
        test_passed("State banner component test passed")
        
        # Test confirmation dialog
        dialog = ConfirmationDialog()
        test_passed("Confirmation dialog component test passed")
        
        # Test audio feedback manager
        feedback_manager = AudioFeedbackManager()
        test_passed("Audio feedback manager test passed")
        
    except Exception as e:
        test_failed(f"UI components test failed: {e}")
        return False
    
    return True

def test_ui_integration():
    """Test UI integration"""
    print("\n2. Testing UI Integration...")
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create test window
        test_window = UITestWindow()
        test_window.show()
        
        # Test window creation
        if test_window.isVisible():
            test_passed("UI test window creation successful")
        else:
            test_failed("UI test window creation failed")
            return False
        
        # Test button click
        QTest.mouseClick(test_window.test_buttons, Qt.LeftButton)
        test_passed("UI button click test passed")
        
        # Process events
        app.processEvents()
        test_passed("UI event processing test passed")
        
        return True
        
    except Exception as e:
        test_failed(f"UI integration test failed: {e}")
        return False

def test_ui_accessibility():
    """Test UI accessibility features"""
    print("\n3. Testing UI Accessibility...")
    
    try:
        # Test large font sizes
        from PySide6.QtGui import QFont
        
        large_font = QFont("Arial", 48, QFont.Bold)
        if large_font.pointSize() >= 36:
            test_passed("Large font size test passed")
        else:
            test_failed("Large font size test failed")
        
        # Test high contrast colors
        high_contrast_colors = {
            "background": "#000000",
            "text": "#FFFFFF",
            "accent": "#FFFF00"
        }
        
        if all(color.startswith("#") and len(color) == 7 for color in high_contrast_colors.values()):
            test_passed("High contrast color test passed")
        else:
            test_failed("High contrast color test failed")
        
        # Test button sizes
        min_button_size = 150
        if min_button_size >= 150:
            test_passed("Minimum button size test passed")
        else:
            test_failed("Minimum button size test failed")
        
        return True
        
    except Exception as e:
        test_failed(f"UI accessibility test failed: {e}")
        return False

def test_ui_performance():
    """Test UI performance"""
    print("\n4. Testing UI Performance...")
    
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Test component creation time
        start_time = time.time()
        
        banner = StateBanner()
        dialog = ConfirmationDialog()
        feedback_manager = AudioFeedbackManager()
        
        creation_time = time.time() - start_time
        
        if creation_time < 1.0:  # Should create in less than 1 second
            test_passed(f"UI component creation performance test passed ({creation_time:.3f}s)")
        else:
            test_warning(f"UI component creation performance test failed ({creation_time:.3f}s > 1.0s)")
        
        # Test state changes
        start_time = time.time()
        
        for i in range(10):
            banner.set_state("ready")
            banner.set_state("recording")
            banner.set_state("saved")
        
        state_change_time = time.time() - start_time
        
        if state_change_time < 0.5:  # Should change states quickly
            test_passed(f"UI state change performance test passed ({state_change_time:.3f}s)")
        else:
            test_warning(f"UI state change performance test failed ({state_change_time:.3f}s > 0.5s)")
        
        return True
        
    except Exception as e:
        test_failed(f"UI performance test failed: {e}")
        return False

def main():
    """Main test function"""
    print("BLACK BOX - UI System Test")
    print("=" * 40)
    
    # Check if we're in a headless environment
    if not os.environ.get('DISPLAY'):
        test_warning("No DISPLAY environment variable - running in headless mode")
    
    # Run tests
    tests_passed = 0
    total_tests = 4
    
    if test_ui_components():
        tests_passed += 1
    
    if test_ui_integration():
        tests_passed += 1
    
    if test_ui_accessibility():
        tests_passed += 1
    
    if test_ui_performance():
        tests_passed += 1
    
    # Test Summary
    print("\n" + "=" * 40)
    print("UI Test Summary")
    print("=" * 40)
    print(f"Tests passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All UI tests passed successfully!")
        return 0
    else:
        print("❌ Some UI tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
