"""
Natural Language Understanding and Intent Resolution
Handles site/service name resolution with heuristics and LLM fallback
"""

import json
import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from rapidfuzz import fuzz, process
from metaphone import doublemetaphone
import subprocess
import tempfile

logger = logging.getLogger(__name__)

@dataclass
class ResolutionResult:
    """Result of site/service name resolution"""
    site: Optional[str]
    confidence: float
    method: str  # 'heuristic', 'llm', 'none'
    original_text: str
    cleaned_text: str

class SiteCatalog:
    """Local catalog of common sites and services"""
    
    def __init__(self, catalog_path: str = "/mnt/nvme/blackbox/data/sites.json"):
        self.catalog_path = catalog_path
        self.sites = {}
        self.load_catalog()
    
    def load_catalog(self) -> None:
        """Load site catalog from JSON file"""
        try:
            if os.path.exists(self.catalog_path):
                with open(self.catalog_path, 'r') as f:
                    data = json.load(f)
                    self.sites = data.get('sites', {})
                logger.info(f"Loaded {len(self.sites)} sites from catalog")
            else:
                # Create default catalog
                self._create_default_catalog()
        except Exception as e:
            logger.error(f"Error loading site catalog: {e}")
            self._create_default_catalog()
    
    def _create_default_catalog(self) -> None:
        """Create default catalog with common sites"""
        self.sites = {
            "gmail": ["gmail", "google mail", "googlemail"],
            "google": ["google", "googol"],
            "facebook": ["facebook", "fb", "face book"],
            "amazon": ["amazon", "amazon.com"],
            "netflix": ["netflix", "net flix"],
            "youtube": ["youtube", "you tube", "yt"],
            "twitter": ["twitter", "x", "tweet"],
            "instagram": ["instagram", "insta", "ig"],
            "linkedin": ["linkedin", "linked in"],
            "paypal": ["paypal", "pay pal"],
            "ebay": ["ebay", "e bay"],
            "spotify": ["spotify", "spot ify"],
            "apple": ["apple", "apple.com", "icloud"],
            "microsoft": ["microsoft", "ms", "outlook", "hotmail"],
            "bank": ["bank", "banking", "chase", "wells fargo", "bank of america"],
            "email": ["email", "e-mail", "mail"],
            "social": ["social media", "social network"],
            "shopping": ["shopping", "store", "retail"],
            "entertainment": ["entertainment", "movie", "music", "video"],
            "news": ["news", "newspaper", "media"]
        }
        
        # Save default catalog
        self.save_catalog()
    
    def save_catalog(self) -> None:
        """Save catalog to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            with open(self.catalog_path, 'w') as f:
                json.dump({"sites": self.sites}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving site catalog: {e}")
    
    def add_site(self, canonical_name: str, aliases: List[str]) -> None:
        """Add a new site with aliases to the catalog"""
        self.sites[canonical_name] = aliases
        self.save_catalog()
    
    def get_all_aliases(self) -> List[str]:
        """Get all aliases from the catalog"""
        aliases = []
        for site_aliases in self.sites.values():
            aliases.extend(site_aliases)
        return aliases

class PasswordCleaner:
    """Rule-based password cleaning for elderly speech patterns"""
    
    def __init__(self):
        # Common phrases to remove from password transcriptions
        self.remove_phrases = [
            r"the password is",
            r"my password is",
            r"the password",
            r"my password",
            r"password is",
            r"it's",
            r"it is",
            r"uh",
            r"um",
            r"er",
            r"ah",
            r"like",
            r"you know",
            r"i mean",
            r"so",
            r"well",
            r"okay",
            r"ok",
            r"right",
            r"yeah",
            r"yes",
            r"no",
            r"the",
            r"a",
            r"an",
            r"and",
            r"or",
            r"but",
            r"for",
            r"with",
            r"by",
            r"from",
            r"to",
            r"in",
            r"on",
            r"at",
            r"of",
            r"is",
            r"are",
            r"was",
            r"were",
            r"be",
            r"been",
            r"being",
            r"have",
            r"has",
            r"had",
            r"do",
            r"does",
            r"did",
            r"will",
            r"would",
            r"could",
            r"should",
            r"may",
            r"might",
            r"can",
            r"must",
            r"shall"
        ]
        
        # Compile regex patterns for efficiency
        self.remove_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.remove_phrases]
    
    def clean_password(self, text: str) -> str:
        """
        Clean password text by removing common speech patterns
        """
        if not text:
            return ""
        
        # Convert to lowercase for processing
        cleaned = text.lower().strip()
        
        # Remove common phrases
        for pattern in self.remove_patterns:
            cleaned = pattern.sub("", cleaned)
        
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove punctuation except for common password characters
        cleaned = re.sub(r'[^\w\s\-_@#$%&*+=]', '', cleaned)
        
        # Remove standalone numbers that might be transcription errors
        words = cleaned.split()
        filtered_words = []
        
        for word in words:
            # Keep words that contain letters or are common password patterns
            if re.search(r'[a-zA-Z]', word) or word in ['123', '456', '789', '000', '111']:
                filtered_words.append(word)
            elif len(word) > 2:  # Keep longer number sequences
                filtered_words.append(word)
        
        cleaned = ' '.join(filtered_words)
        
        # Final cleanup
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

class HeuristicResolver:
    """Deterministic heuristics for site name resolution"""
    
    def __init__(self, site_catalog: SiteCatalog):
        self.catalog = site_catalog
        self.cleaner = PasswordCleaner()
    
    def resolve_site(self, text: str) -> ResolutionResult:
        """
        Resolve site name using deterministic heuristics
        Returns ResolutionResult with confidence score
        """
        if not text:
            return ResolutionResult(None, 0.0, "none", text, "")
        
        # Clean the input text
        cleaned = self._normalize_text(text)
        
        # Try different resolution strategies
        strategies = [
            self._exact_match,
            self._fuzzy_match,
            self._phonetic_match,
            self._partial_match
        ]
        
        best_result = ResolutionResult(None, 0.0, "heuristic", text, cleaned)
        
        for strategy in strategies:
            result = strategy(cleaned)
            if result.confidence > best_result.confidence:
                best_result = result
        
        return best_result
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        normalized = text.lower().strip()
        
        # Remove common suffixes
        normalized = re.sub(r'\s+(dot\s+)?com$', '', normalized)
        normalized = re.sub(r'\s+(dot\s+)?org$', '', normalized)
        normalized = re.sub(r'\s+(dot\s+)?net$', '', normalized)
        normalized = re.sub(r'\s+(dot\s+)?edu$', '', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _exact_match(self, text: str) -> ResolutionResult:
        """Try exact match against catalog"""
        all_aliases = self.catalog.get_all_aliases()
        
        if text in all_aliases:
            # Find the canonical name
            for canonical, aliases in self.catalog.sites.items():
                if text in aliases:
                    return ResolutionResult(
                        site=canonical,
                        confidence=1.0,
                        method="heuristic",
                        original_text=text,
                        cleaned_text=text
                    )
        
        return ResolutionResult(None, 0.0, "heuristic", text, text)
    
    def _fuzzy_match(self, text: str) -> ResolutionResult:
        """Try fuzzy string matching"""
        all_aliases = self.catalog.get_all_aliases()
        
        if not all_aliases:
            return ResolutionResult(None, 0.0, "heuristic", text, text)
        
        # Use rapidfuzz for fast fuzzy matching
        best_match = process.extractOne(text, all_aliases, scorer=fuzz.ratio)
        
        if best_match and best_match[1] >= 82:  # 82% threshold
            # Find canonical name
            for canonical, aliases in self.catalog.sites.items():
                if best_match[0] in aliases:
                    return ResolutionResult(
                        site=canonical,
                        confidence=best_match[1] / 100.0,
                        method="heuristic",
                        original_text=text,
                        cleaned_text=text
                    )
        
        return ResolutionResult(None, 0.0, "heuristic", text, text)
    
    def _phonetic_match(self, text: str) -> ResolutionResult:
        """Try phonetic matching using Double Metaphone"""
        text_phonetic = doublemetaphone(text)
        
        best_score = 0.0
        best_site = None
        
        for canonical, aliases in self.catalog.sites.items():
            for alias in aliases:
                alias_phonetic = doublemetaphone(alias)
                
                # Compare phonetic codes
                if text_phonetic[0] and alias_phonetic[0]:
                    if text_phonetic[0] == alias_phonetic[0]:
                        score = 0.9
                    elif text_phonetic[1] and alias_phonetic[1] and text_phonetic[1] == alias_phonetic[1]:
                        score = 0.8
                    else:
                        continue
                    
                    if score > best_score:
                        best_score = score
                        best_site = canonical
        
        if best_score >= 0.8:
            return ResolutionResult(
                site=best_site,
                confidence=best_score,
                method="heuristic",
                original_text=text,
                cleaned_text=text
            )
        
        return ResolutionResult(None, 0.0, "heuristic", text, text)
    
    def _partial_match(self, text: str) -> ResolutionResult:
        """Try partial string matching"""
        words = text.split()
        best_score = 0.0
        best_site = None
        
        for canonical, aliases in self.catalog.sites.items():
            for alias in aliases:
                alias_words = alias.split()
                
                # Check if any words match
                matches = 0
                for word in words:
                    for alias_word in alias_words:
                        if word in alias_word or alias_word in word:
                            matches += 1
                            break
                
                if matches > 0:
                    score = matches / max(len(words), len(alias_words))
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_site = canonical
        
        if best_score >= 0.6:
            return ResolutionResult(
                site=best_site,
                confidence=best_score,
                method="heuristic",
                original_text=text,
                cleaned_text=text
            )
        
        return ResolutionResult(None, 0.0, "heuristic", text, text)

class LLMResolver:
    """LLM-based site resolution using TensorRT-LLM"""
    
    def __init__(self, model_path: str = "/mnt/nvme/blackbox/models/llm/"):
        self.model_path = model_path
        self.is_available = self._check_llm_availability()
    
    def _check_llm_availability(self) -> bool:
        """Check if TensorRT-LLM is available"""
        try:
            # Check if TensorRT-LLM is installed
            result = subprocess.run(
                ["python", "-c", "import tensorrt_llm"],
                capture_output=True,
                timeout=5.0
            )
            return result.returncode == 0
        except:
            return False
    
    def resolve_site(self, text: str) -> ResolutionResult:
        """
        Resolve site name using LLM
        Returns strict JSON format: {"site": "<domain|null>", "confidence": 0.xx}
        """
        if not self.is_available:
            return ResolutionResult(None, 0.0, "llm", text, text)
        
        try:
            # Create prompt for site resolution
            prompt = self._create_prompt(text)
            
            # Call LLM (placeholder for TensorRT-LLM integration)
            response = self._call_llm(prompt)
            
            # Parse JSON response
            result = self._parse_llm_response(response)
            
            return ResolutionResult(
                site=result.get("site"),
                confidence=result.get("confidence", 0.0),
                method="llm",
                original_text=text,
                cleaned_text=text
            )
            
        except Exception as e:
            logger.error(f"LLM resolution error: {e}")
            return ResolutionResult(None, 0.0, "llm", text, text)
    
    def _create_prompt(self, text: str) -> str:
        """Create prompt for site resolution"""
        return f"""You are a helpful assistant that identifies website or service names from spoken text.

Input: "{text}"

Identify the most likely website or service name. Consider common variations, mispronunciations, and abbreviations.

Respond with ONLY a JSON object in this exact format:
{{"site": "<domain_name_or_null>", "confidence": 0.xx}}

Examples:
- "gmail" → {{"site": "gmail", "confidence": 0.95}}
- "facebook" → {{"site": "facebook", "confidence": 0.90}}
- "amazon dot com" → {{"site": "amazon", "confidence": 0.88}}
- "my bank" → {{"site": "bank", "confidence": 0.75}}
- "some random text" → {{"site": null, "confidence": 0.20}}

Response:"""
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM using TensorRT-LLM (placeholder implementation)"""
        # This is a placeholder for actual TensorRT-LLM integration
        # In a real implementation, you would:
        # 1. Load the model using TensorRT-LLM
        # 2. Tokenize the prompt
        # 3. Run inference
        # 4. Decode the response
        
        # For now, return a mock response
        return '{"site": null, "confidence": 0.0}'
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[^}]*\}', response)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
        
        return {"site": None, "confidence": 0.0}

class IntentResolver:
    """Main intent resolution system"""
    
    def __init__(self):
        self.site_catalog = SiteCatalog()
        self.heuristic_resolver = HeuristicResolver(self.site_catalog)
        self.llm_resolver = LLMResolver()
        self.password_cleaner = PasswordCleaner()
    
    def resolve_intent(self, text: str, ui_state: str) -> Dict[str, Any]:
        """
        Resolve intent and entities from text
        Args:
            text: Transcribed text
            ui_state: Current UI state ("save", "retrieve", "cancel")
        Returns:
            Dict with intent, entities, and confidence
        """
        start_time = time.time()
        
        # Intent is determined by UI state
        intent = ui_state.lower()
        
        # Extract entities (site name, password)
        entities = self._extract_entities(text, intent)
        
        processing_time = time.time() - start_time
        
        return {
            "intent": intent,
            "entities": entities,
            "confidence": entities.get("site_confidence", 0.0),
            "processing_time": processing_time,
            "original_text": text
        }
    
    def _extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """Extract entities from text based on intent"""
        entities = {}
        
        if intent in ["save", "retrieve"]:
            # Extract site name
            site_result = self._resolve_site_name(text)
            entities["site"] = site_result.site
            entities["site_confidence"] = site_result.confidence
            entities["site_method"] = site_result.method
            
            # Extract password (for save intent)
            if intent == "save":
                password = self._extract_password(text)
                entities["password"] = password
        
        return entities
    
    def _resolve_site_name(self, text: str) -> ResolutionResult:
        """Resolve site name using heuristics and LLM fallback"""
        # Try heuristics first
        heuristic_result = self.heuristic_resolver.resolve_site(text)
        
        # If confidence is high enough, return heuristic result
        if heuristic_result.confidence >= 0.82:
            return heuristic_result
        
        # If confidence is too low, try LLM
        if heuristic_result.confidence < 0.65:
            llm_result = self.llm_resolver.resolve_site(text)
            
            # If LLM confidence is higher, use LLM result
            if llm_result.confidence > heuristic_result.confidence:
                return llm_result
        
        # Return heuristic result (even if low confidence)
        return heuristic_result
    
    def _extract_password(self, text: str) -> str:
        """Extract password from text"""
        # Clean the text to extract password
        cleaned = self.password_cleaner.clean_password(text)
        
        # Remove site name if present
        # This is a simple approach - in practice, you might want more sophisticated parsing
        words = cleaned.split()
        if len(words) > 1:
            # Assume password is the last part of the text
            # In a real implementation, you'd use more sophisticated parsing
            return " ".join(words[-3:])  # Take last 3 words as password
        
        return cleaned
    
    def get_resolution_confidence(self, result: ResolutionResult) -> str:
        """Get confidence level description"""
        if result.confidence >= 0.85:
            return "high"
        elif result.confidence >= 0.65:
            return "medium"
        else:
            return "low"
