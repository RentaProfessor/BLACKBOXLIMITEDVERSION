"""
Warm Piper TTS service with health checks
Long-running Piper process wrapper to avoid startup cost
Health check endpoint /tts/health
"""

import os
import subprocess
import tempfile
import threading
import time
import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path
import queue
import signal
import sys

logger = logging.getLogger(__name__)

class PiperTTSServer:
    """Warm Piper TTS service with health checks"""
    
    def __init__(self, 
                 model_path: str = "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx",
                 config_path: str = "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx.json",
                 port: int = 8080):
        self.model_path = model_path
        self.config_path = config_path
        self.port = port
        self.is_running = False
        self.server_thread = None
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.health_status = "stopped"
        self.startup_time = 0
        self.request_count = 0
        self.error_count = 0
        
        # Verify model files exist
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Piper model not found at {self.model_path}")
        
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Piper config not found at {self.config_path}")
    
    def start(self) -> bool:
        """Start the TTS server"""
        if self.is_running:
            logger.warning("TTS server is already running")
            return True
        
        try:
            self.is_running = True
            self.health_status = "starting"
            self.startup_time = time.time()
            
            # Start server thread
            self.server_thread = threading.Thread(target=self._server_worker, daemon=True)
            self.server_thread.start()
            
            # Wait for startup
            time.sleep(2)
            
            if self.health_status == "healthy":
                logger.info("TTS server started successfully")
                return True
            else:
                logger.error("TTS server failed to start")
                self.stop()
                return False
                
        except Exception as e:
            logger.error(f"Error starting TTS server: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the TTS server"""
        self.is_running = False
        self.health_status = "stopping"
        
        if self.server_thread:
            self.server_thread.join(timeout=5.0)
        
        self.health_status = "stopped"
        logger.info("TTS server stopped")
    
    def _server_worker(self):
        """Main server worker thread"""
        try:
            # Test Piper initialization
            if self._test_piper():
                self.health_status = "healthy"
                logger.info("TTS server is healthy and ready")
            else:
                self.health_status = "unhealthy"
                logger.error("TTS server failed health check")
                return
            
            # Main server loop
            while self.is_running:
                try:
                    # Process requests
                    self._process_requests()
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error in server worker: {e}")
                    self.error_count += 1
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"Fatal error in server worker: {e}")
            self.health_status = "unhealthy"
        finally:
            self.is_running = False
    
    def _test_piper(self) -> bool:
        """Test Piper initialization"""
        try:
            # Test with a simple phrase
            test_text = "Hello"
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            cmd = [
                "piper",
                "--model", self.model_path,
                "--config", self.config_path,
                "--output_file", temp_path
            ]
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=test_text, timeout=10.0)
            
            if process.returncode == 0 and os.path.exists(temp_path):
                os.unlink(temp_path)
                return True
            else:
                logger.error(f"Piper test failed: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error testing Piper: {e}")
            return False
    
    def _process_requests(self):
        """Process queued requests"""
        try:
            # Check for new requests
            while not self.request_queue.empty():
                request = self.request_queue.get_nowait()
                self._handle_request(request)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Error processing requests: {e}")
    
    def _handle_request(self, request: Dict[str, Any]):
        """Handle a single request"""
        try:
            request_type = request.get("type")
            
            if request_type == "synthesize":
                self._handle_synthesize_request(request)
            elif request_type == "health":
                self._handle_health_request(request)
            else:
                logger.warning(f"Unknown request type: {request_type}")
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self.error_count += 1
    
    def _handle_synthesize_request(self, request: Dict[str, Any]):
        """Handle synthesis request"""
        try:
            text = request.get("text", "")
            request_id = request.get("id", "")
            
            if not text:
                self._send_response(request_id, {"error": "No text provided"})
                return
            
            # Synthesize text
            audio_path = self._synthesize_text(text)
            
            if audio_path:
                self._send_response(request_id, {"success": True, "audio_path": audio_path})
                self.request_count += 1
            else:
                self._send_response(request_id, {"error": "Synthesis failed"})
                self.error_count += 1
                
        except Exception as e:
            logger.error(f"Error in synthesis request: {e}")
            self._send_response(request.get("id", ""), {"error": str(e)})
            self.error_count += 1
    
    def _handle_health_request(self, request: Dict[str, Any]):
        """Handle health check request"""
        try:
            request_id = request.get("id", "")
            
            health_info = {
                "status": self.health_status,
                "uptime": time.time() - self.startup_time if self.startup_time > 0 else 0,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "model_path": self.model_path,
                "config_path": self.config_path
            }
            
            self._send_response(request_id, {"health": health_info})
            
        except Exception as e:
            logger.error(f"Error in health request: {e}")
            self._send_response(request.get("id", ""), {"error": str(e)})
    
    def _synthesize_text(self, text: str) -> Optional[str]:
        """Synthesize text to audio file"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            cmd = [
                "piper",
                "--model", self.model_path,
                "--config", self.config_path,
                "--output_file", temp_path
            ]
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=5.0)
            
            if process.returncode == 0 and os.path.exists(temp_path):
                return temp_path
            else:
                logger.error(f"Piper synthesis failed: {stderr}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Piper synthesis timeout")
            return None
        except Exception as e:
            logger.error(f"Error synthesizing text: {e}")
            return None
    
    def _send_response(self, request_id: str, response: Dict[str, Any]):
        """Send response to client"""
        try:
            self.response_queue.put({
                "id": request_id,
                "response": response,
                "timestamp": time.time()
            })
        except Exception as e:
            logger.error(f"Error sending response: {e}")
    
    def synthesize(self, text: str, timeout: float = 5.0) -> Optional[str]:
        """Synthesize text (client interface)"""
        if not self.is_running or self.health_status != "healthy":
            logger.warning("TTS server is not healthy")
            return None
        
        try:
            request_id = f"req_{int(time.time() * 1000)}"
            request = {
                "type": "synthesize",
                "text": text,
                "id": request_id
            }
            
            # Send request
            self.request_queue.put(request)
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    response = self.response_queue.get_nowait()
                    if response["id"] == request_id:
                        if "error" in response["response"]:
                            logger.error(f"Synthesis error: {response['response']['error']}")
                            return None
                        return response["response"].get("audio_path")
                except queue.Empty:
                    time.sleep(0.1)
            
            logger.error("Synthesis request timeout")
            return None
            
        except Exception as e:
            logger.error(f"Error in synthesis request: {e}")
            return None
    
    def get_health(self) -> Dict[str, Any]:
        """Get server health status"""
        if not self.is_running:
            return {"status": "stopped"}
        
        try:
            request_id = f"health_{int(time.time() * 1000)}"
            request = {
                "type": "health",
                "id": request_id
            }
            
            # Send request
            self.request_queue.put(request)
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < 2.0:
                try:
                    response = self.response_queue.get_nowait()
                    if response["id"] == request_id:
                        return response["response"].get("health", {"status": "unknown"})
                except queue.Empty:
                    time.sleep(0.1)
            
            return {"status": "timeout"}
            
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"status": "error", "error": str(e)}

class PiperTTSClient:
    """Client for Piper TTS server with fallback"""
    
    def __init__(self, server: Optional[PiperTTSServer] = None):
        self.server = server
        self.fallback_enabled = True
    
    def speak(self, text: str) -> bool:
        """Speak text using server or fallback"""
        if self.server and self.server.health_status == "healthy":
            # Use server
            audio_path = self.server.synthesize(text)
            if audio_path:
                return self._play_audio_file(audio_path)
        
        # Fallback to one-shot CLI
        if self.fallback_enabled:
            return self._fallback_speak(text)
        
        return False
    
    def _play_audio_file(self, audio_path: str) -> bool:
        """Play audio file using ALSA"""
        try:
            # Use aplay to play the audio file
            result = subprocess.run([
                "aplay", audio_path
            ], capture_output=True, timeout=10)
            
            # Clean up temporary file
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Error playing audio file: {e}")
            return False
    
    def _fallback_speak(self, text: str) -> bool:
        """Fallback to one-shot Piper CLI"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            cmd = [
                "piper",
                "--model", "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx",
                "--config", "/mnt/nvme/blackbox/models/piper/en_US-lessac-medium.onnx.json",
                "--output_file", temp_path
            ]
            
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=text, timeout=5.0)
            
            if process.returncode == 0 and os.path.exists(temp_path):
                success = self._play_audio_file(temp_path)
                return success
            else:
                logger.error(f"Fallback synthesis failed: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error in fallback synthesis: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get TTS status"""
        if self.server:
            return self.server.get_health()
        else:
            return {"status": "no_server"}

def main():
    """Test TTS server"""
    import signal
    
    def signal_handler(signum, frame):
        print("Shutting down TTS server...")
        if 'server' in globals():
            server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start server
    server = PiperTTSServer()
    
    if server.start():
        print("TTS server started successfully")
        
        # Test client
        client = PiperTTSClient(server)
        
        # Test synthesis
        print("Testing synthesis...")
        if client.speak("Hello, this is a test of the TTS server."):
            print("Synthesis test passed")
        else:
            print("Synthesis test failed")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
                health = server.get_health()
                print(f"Health: {health}")
        except KeyboardInterrupt:
            pass
    else:
        print("Failed to start TTS server")
    
    server.stop()

if __name__ == "__main__":
    main()
