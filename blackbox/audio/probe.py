"""
Audio device probing and configuration
Discovers and maps audio devices by name for reliable selection
"""

import os
import json
import subprocess
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioDeviceProbe:
    """Probe and configure audio devices"""
    
    def __init__(self, config_path: str = "/mnt/nvme/blackbox/config/audio.json"):
        self.config_path = config_path
        self.devices = {}
        self.load_config()
    
    def probe_devices(self) -> Dict[str, Dict]:
        """Probe all available audio devices"""
        devices = {
            'input': self._probe_input_devices(),
            'output': self._probe_output_devices()
        }
        
        # Save configuration
        self.save_config(devices)
        
        return devices
    
    def _probe_input_devices(self) -> List[Dict]:
        """Probe input devices using arecord -l"""
        try:
            result = subprocess.run(
                ['arecord', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"arecord -l failed: {result.stderr}")
                return []
            
            return self._parse_arecord_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.error("arecord -l timeout")
            return []
        except Exception as e:
            logger.error(f"Error probing input devices: {e}")
            return []
    
    def _probe_output_devices(self) -> List[Dict]:
        """Probe output devices using aplay -l"""
        try:
            result = subprocess.run(
                ['aplay', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"aplay -l failed: {result.stderr}")
                return []
            
            return self._parse_aplay_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.error("aplay -l timeout")
            return []
        except Exception as e:
            logger.error(f"Error probing output devices: {e}")
            return []
    
    def _parse_arecord_output(self, output: str) -> List[Dict]:
        """Parse arecord -l output"""
        devices = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if 'card' in line and 'device' in line:
                # Parse line like: "card 1: USB [USB PnP Sound Device], device 0: USB Audio [USB Audio]"
                parts = line.split(',')
                if len(parts) >= 2:
                    card_part = parts[0].strip()
                    device_part = parts[1].strip()
                    
                    # Extract card number
                    card_num = None
                    if 'card' in card_part:
                        try:
                            card_num = int(card_part.split('card')[1].split(':')[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    # Extract device number
                    device_num = None
                    if 'device' in device_part:
                        try:
                            device_num = int(device_part.split('device')[1].split(':')[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    # Extract device name
                    device_name = None
                    if '[' in device_part and ']' in device_part:
                        device_name = device_part.split('[')[1].split(']')[0]
                    
                    if card_num is not None and device_num is not None and device_name:
                        devices.append({
                            'card': card_num,
                            'device': device_num,
                            'name': device_name,
                            'hw_id': f"hw:{card_num},{device_num}",
                            'type': 'input'
                        })
        
        return devices
    
    def _parse_aplay_output(self, output: str) -> List[Dict]:
        """Parse aplay -l output"""
        devices = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if 'card' in line and 'device' in line:
                # Parse line like: "card 1: USB [USB PnP Sound Device], device 0: USB Audio [USB Audio]"
                parts = line.split(',')
                if len(parts) >= 2:
                    card_part = parts[0].strip()
                    device_part = parts[1].strip()
                    
                    # Extract card number
                    card_num = None
                    if 'card' in card_part:
                        try:
                            card_num = int(card_part.split('card')[1].split(':')[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    # Extract device number
                    device_num = None
                    if 'device' in device_part:
                        try:
                            device_num = int(device_part.split('device')[1].split(':')[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    # Extract device name
                    device_name = None
                    if '[' in device_part and ']' in device_part:
                        device_name = device_part.split('[')[1].split(']')[0]
                    
                    if card_num is not None and device_num is not None and device_name:
                        devices.append({
                            'card': card_num,
                            'device': device_num,
                            'name': device_name,
                            'hw_id': f"hw:{card_num},{device_num}",
                            'type': 'output'
                        })
        
        return devices
    
    def find_device_by_name(self, device_name: str, device_type: str) -> Optional[Dict]:
        """Find device by name"""
        devices = self.devices.get(device_type, [])
        
        for device in devices:
            if device_name.lower() in device['name'].lower():
                return device
        
        return None
    
    def get_default_devices(self) -> Dict[str, Optional[Dict]]:
        """Get default input and output devices"""
        input_devices = self.devices.get('input', [])
        output_devices = self.devices.get('output', [])
        
        # Prefer USB devices
        usb_input = None
        usb_output = None
        
        for device in input_devices:
            if 'usb' in device['name'].lower():
                usb_input = device
                break
        
        for device in output_devices:
            if 'usb' in device['name'].lower():
                usb_output = device
                break
        
        # Fallback to first available device
        return {
            'input': usb_input or (input_devices[0] if input_devices else None),
            'output': usb_output or (output_devices[0] if output_devices else None)
        }
    
    def save_config(self, devices: Dict[str, List[Dict]]) -> None:
        """Save device configuration to JSON file"""
        try:
            # Create config directory
            config_dir = os.path.dirname(self.config_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # Save configuration
            with open(self.config_path, 'w') as f:
                json.dump(devices, f, indent=2)
            
            self.devices = devices
            logger.info(f"Audio device configuration saved to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save audio configuration: {e}")
    
    def load_config(self) -> None:
        """Load device configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.devices = json.load(f)
                logger.info(f"Audio device configuration loaded from {self.config_path}")
            else:
                self.devices = {'input': [], 'output': []}
                logger.info("No audio configuration found, will probe devices")
                
        except Exception as e:
            logger.error(f"Failed to load audio configuration: {e}")
            self.devices = {'input': [], 'output': []}
    
    def test_device(self, device: Dict) -> bool:
        """Test if a device is working"""
        if device['type'] == 'input':
            return self._test_input_device(device)
        else:
            return self._test_output_device(device)
    
    def _test_input_device(self, device: Dict) -> bool:
        """Test input device by recording a short sample"""
        try:
            # Record 1 second of audio
            result = subprocess.run([
                'arecord',
                '-D', device['hw_id'],
                '-f', 'S16_LE',
                '-r', '16000',
                '-c', '1',
                '-d', '1',
                '/tmp/test_input.wav'
            ], capture_output=True, timeout=5)
            
            # Check if file was created and has content
            if result.returncode == 0 and os.path.exists('/tmp/test_input.wav'):
                file_size = os.path.getsize('/tmp/test_input.wav')
                os.unlink('/tmp/test_input.wav')
                return file_size > 0
            
            return False
            
        except Exception as e:
            logger.error(f"Error testing input device {device['name']}: {e}")
            return False
    
    def _test_output_device(self, device: Dict) -> bool:
        """Test output device by playing a test tone"""
        try:
            # Generate a test tone
            result = subprocess.run([
                'speaker-test',
                '-D', device['hw_id'],
                '-c', '1',
                '-t', 'sine',
                '-f', '1000',
                '-l', '1'
            ], capture_output=True, timeout=5)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error testing output device {device['name']}: {e}")
            return False

def main():
    """Main function for testing"""
    probe = AudioDeviceProbe()
    devices = probe.probe_devices()
    
    print("Audio Device Probe Results:")
    print("=" * 40)
    
    print("\nInput Devices:")
    for device in devices.get('input', []):
        print(f"  Card {device['card']}, Device {device['device']}: {device['name']}")
        print(f"    HW ID: {device['hw_id']}")
    
    print("\nOutput Devices:")
    for device in devices.get('output', []):
        print(f"  Card {device['card']}, Device {device['device']}: {device['name']}")
        print(f"    HW ID: {device['hw_id']}")
    
    print("\nDefault Devices:")
    defaults = probe.get_default_devices()
    if defaults['input']:
        print(f"  Input: {defaults['input']['name']} ({defaults['input']['hw_id']})")
    else:
        print("  Input: No device found")
    
    if defaults['output']:
        print(f"  Output: {defaults['output']['name']} ({defaults['output']['hw_id']})")
    else:
        print("  Output: No device found")

if __name__ == "__main__":
    main()
