"""
Optional tiny LLM normalizer with strict JSON schema
Input: {"transcripts":[...], "catalog":[...], "hints":{...}}
Output: {"site":"<domain|null>","confidence":0.xx}
Feature flag controlled, max_new_tokens=16, temperature=0.0
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LLMConfig:
    """LLM configuration"""
    enabled: bool = False
    model_path: str = "/mnt/nvme/blackbox/models/llm/"
    max_new_tokens: int = 16
    temperature: float = 0.0
    timeout_seconds: int = 5
    confidence_threshold: float = 0.85

class LLMNormalizer:
    """Tiny LLM normalizer for site name resolution"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.is_available = False
        
        if self.config.enabled:
            self.is_available = self._check_llm_availability()
    
    def _check_llm_availability(self) -> bool:
        """Check if LLM is available"""
        try:
            # Check if TensorRT-LLM is available
            import tensorrt_llm
            return True
        except ImportError:
            logger.warning("TensorRT-LLM not available, LLM normalizer disabled")
            return False
    
    def normalize_site(self, transcripts: List[str], 
                      catalog: List[str], 
                      hints: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Normalize site name using LLM
        Args:
            transcripts: List of transcriptions to normalize
            catalog: List of available site names
            hints: Additional hints for normalization
        Returns:
            Dict with site and confidence
        """
        if not self.is_available or not self.config.enabled:
            return {"site": None, "confidence": 0.0}
        
        try:
            # Create input prompt
            input_data = {
                "transcripts": transcripts,
                "catalog": catalog,
                "hints": hints or {}
            }
            
            # Call LLM
            response = self._call_llm(input_data)
            
            # Parse and validate response
            result = self._parse_response(response)
            
            return result
            
        except Exception as e:
            logger.error(f"LLM normalization error: {e}")
            return {"site": None, "confidence": 0.0}
    
    def _call_llm(self, input_data: Dict[str, Any]) -> str:
        """Call LLM with input data"""
        # This is a placeholder for actual TensorRT-LLM integration
        # In a real implementation, you would:
        # 1. Load the model using TensorRT-LLM
        # 2. Tokenize the input
        # 3. Run inference with constraints
        # 4. Decode the response
        
        # For now, return a mock response
        return '{"site": null, "confidence": 0.0}'
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse and validate LLM response"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^}]*\}', response)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # Validate response schema
                if self._validate_response_schema(result):
                    return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
        
        return {"site": None, "confidence": 0.0}
    
    def _validate_response_schema(self, result: Dict[str, Any]) -> bool:
        """Validate response schema"""
        required_fields = ["site", "confidence"]
        
        for field in required_fields:
            if field not in result:
                return False
        
        # Validate confidence is a float between 0 and 1
        if not isinstance(result["confidence"], (int, float)):
            return False
        
        if not 0 <= result["confidence"] <= 1:
            return False
        
        # Validate site is string or null
        if result["site"] is not None and not isinstance(result["site"], str):
            return False
        
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get LLM normalizer status"""
        return {
            "enabled": self.config.enabled,
            "available": self.is_available,
            "model_path": self.config.model_path,
            "max_new_tokens": self.config.max_new_tokens,
            "temperature": self.config.temperature
        }

class LLMNormalizerManager:
    """Manager for LLM normalizer with feature flag support"""
    
    def __init__(self, config_path: str = "/mnt/nvme/blackbox/config/app.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.normalizer = LLMNormalizer(self.config)
    
    def _load_config(self) -> LLMConfig:
        """Load configuration from YAML file"""
        try:
            import yaml
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                llm_config = config_data.get('llm', {})
                return LLMConfig(
                    enabled=llm_config.get('enabled', False),
                    model_path=llm_config.get('model_path', "/mnt/nvme/blackbox/models/llm/"),
                    max_new_tokens=llm_config.get('max_new_tokens', 16),
                    temperature=llm_config.get('temperature', 0.0),
                    timeout_seconds=llm_config.get('timeout_seconds', 5),
                    confidence_threshold=llm_config.get('confidence_threshold', 0.85)
                )
        except Exception as e:
            logger.error(f"Error loading LLM config: {e}")
        
        return LLMConfig()
    
    def normalize_site(self, transcripts: List[str], 
                      catalog: List[str], 
                      hints: Dict[str, Any] = None) -> Dict[str, Any]:
        """Normalize site name using LLM if enabled"""
        if not self.config.enabled:
            return {"site": None, "confidence": 0.0}
        
        return self.normalizer.normalize_site(transcripts, catalog, hints)
    
    def is_enabled(self) -> bool:
        """Check if LLM normalizer is enabled"""
        return self.config.enabled and self.normalizer.is_available
    
    def get_status(self) -> Dict[str, Any]:
        """Get normalizer status"""
        return self.normalizer.get_status()

def main():
    """Main function for testing"""
    manager = LLMNormalizerManager()
    
    print("LLM Normalizer Test")
    print("=" * 30)
    
    # Show status
    status = manager.get_status()
    print(f"Enabled: {status['enabled']}")
    print(f"Available: {status['available']}")
    print(f"Model Path: {status['model_path']}")
    
    if manager.is_enabled():
        # Test normalization
        transcripts = ["gmail", "google mail", "g mail"]
        catalog = ["gmail", "google", "facebook", "amazon"]
        hints = {"context": "email service"}
        
        result = manager.normalize_site(transcripts, catalog, hints)
        print(f"Normalization result: {result}")
    else:
        print("LLM normalizer is disabled or not available")

if __name__ == "__main__":
    main()
