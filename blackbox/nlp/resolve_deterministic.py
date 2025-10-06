"""
Deterministic-first resolver with local catalog
Normalization, rapidfuzz + Double Metaphone scoring
Thresholds: accept ≥0.88; LLM normalizer call only if <0.82
"""

import json
import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from rapidfuzz import fuzz, process
from metaphone import doublemetaphone

logger = logging.getLogger(__name__)

@dataclass
class ResolutionResult:
    """Result of site name resolution"""
    site: Optional[str]
    confidence: float
    method: str
    original_text: str
    cleaned_text: str
    needs_confirmation: bool = False

class DeterministicResolver:
    """Deterministic site name resolver with local catalog"""
    
    def __init__(self, catalog_path: str = "/mnt/nvme/blackbox/catalog/sites.json"):
        self.catalog_path = catalog_path
        self.sites = {}
        self.accept_threshold = 0.88
        self.llm_threshold = 0.82
        self.confirmation_threshold = 0.75
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
                logger.error(f"Site catalog not found at {self.catalog_path}")
                self.sites = {}
        except Exception as e:
            logger.error(f"Error loading site catalog: {e}")
            self.sites = {}
    
    def resolve_site(self, text: str) -> ResolutionResult:
        """
        Resolve site name using deterministic methods
        Returns ResolutionResult with confidence and method
        """
        if not text:
            return ResolutionResult(None, 0.0, "none", text, "")
        
        # Clean and normalize text
        cleaned = self._normalize_text(text)
        
        # Try different resolution strategies
        strategies = [
            self._exact_match,
            self._fuzzy_match,
            self._phonetic_match,
            self._partial_match
        ]
        
        best_result = ResolutionResult(None, 0.0, "deterministic", text, cleaned)
        
        for strategy in strategies:
            result = strategy(cleaned)
            if result.confidence > best_result.confidence:
                best_result = result
        
        # Determine if confirmation is needed
        if best_result.confidence >= self.accept_threshold:
            best_result.needs_confirmation = False
        elif best_result.confidence >= self.confirmation_threshold:
            best_result.needs_confirmation = True
        else:
            best_result.needs_confirmation = False
        
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
        normalized = re.sub(r'\s+(dot\s+)?gov$', '', normalized)
        normalized = re.sub(r'\s+(dot\s+)?mil$', '', normalized)
        
        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _exact_match(self, text: str) -> ResolutionResult:
        """Try exact match against catalog"""
        all_aliases = self._get_all_aliases()
        
        if text in all_aliases:
            # Find the canonical name
            for canonical, aliases in self.sites.items():
                if text in aliases:
                    return ResolutionResult(
                        site=canonical,
                        confidence=1.0,
                        method="exact_match",
                        original_text=text,
                        cleaned_text=text
                    )
        
        return ResolutionResult(None, 0.0, "exact_match", text, text)
    
    def _fuzzy_match(self, text: str) -> ResolutionResult:
        """Try fuzzy string matching"""
        all_aliases = self._get_all_aliases()
        
        if not all_aliases:
            return ResolutionResult(None, 0.0, "fuzzy_match", text, text)
        
        # Use rapidfuzz for fast fuzzy matching
        best_match = process.extractOne(text, all_aliases, scorer=fuzz.ratio)
        
        if best_match and best_match[1] >= 70:  # 70% threshold for fuzzy match
            # Find canonical name
            for canonical, aliases in self.sites.items():
                if best_match[0] in aliases:
                    confidence = best_match[1] / 100.0
                    return ResolutionResult(
                        site=canonical,
                        confidence=confidence,
                        method="fuzzy_match",
                        original_text=text,
                        cleaned_text=text
                    )
        
        return ResolutionResult(None, 0.0, "fuzzy_match", text, text)
    
    def _phonetic_match(self, text: str) -> ResolutionResult:
        """Try phonetic matching using Double Metaphone"""
        text_phonetic = doublemetaphone(text)
        
        best_score = 0.0
        best_site = None
        
        for canonical, aliases in self.sites.items():
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
                method="phonetic_match",
                original_text=text,
                cleaned_text=text
            )
        
        return ResolutionResult(None, 0.0, "phonetic_match", text, text)
    
    def _partial_match(self, text: str) -> ResolutionResult:
        """Try partial string matching"""
        words = text.split()
        best_score = 0.0
        best_site = None
        
        for canonical, aliases in self.sites.items():
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
                method="partial_match",
                original_text=text,
                cleaned_text=text
            )
        
        return ResolutionResult(None, 0.0, "partial_match", text, text)
    
    def _get_all_aliases(self) -> List[str]:
        """Get all aliases from the catalog"""
        aliases = []
        for site_aliases in self.sites.values():
            aliases.extend(site_aliases)
        return aliases
    
    def get_site_info(self, site: str) -> Optional[Dict]:
        """Get information about a site"""
        if site in self.sites:
            return {
                'canonical_name': site,
                'aliases': self.sites[site],
                'alias_count': len(self.sites[site])
            }
        return None
    
    def add_site(self, canonical_name: str, aliases: List[str]) -> None:
        """Add a new site with aliases to the catalog"""
        self.sites[canonical_name] = aliases
        self.save_catalog()
    
    def save_catalog(self) -> None:
        """Save catalog to JSON file"""
        try:
            os.makedirs(os.path.dirname(self.catalog_path), exist_ok=True)
            with open(self.catalog_path, 'w') as f:
                json.dump({"sites": self.sites}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving site catalog: {e}")
    
    def get_catalog_stats(self) -> Dict:
        """Get catalog statistics"""
        total_sites = len(self.sites)
        total_aliases = sum(len(aliases) for aliases in self.sites.values())
        
        return {
            'total_sites': total_sites,
            'total_aliases': total_aliases,
            'average_aliases_per_site': total_aliases / total_sites if total_sites > 0 else 0
        }

class AmbiguityHandler:
    """Handle ambiguous site resolution results"""
    
    def __init__(self):
        self.pending_confirmations = {}
    
    def needs_confirmation(self, result: ResolutionResult) -> bool:
        """Check if result needs user confirmation"""
        return result.needs_confirmation
    
    def create_confirmation_prompt(self, result: ResolutionResult) -> str:
        """Create confirmation prompt for ambiguous result"""
        if result.site:
            return f"Did you mean '{result.site}'? (Confidence: {result.confidence:.2f})"
        else:
            return "I didn't recognize that site. Please try again."
    
    def handle_confirmation(self, result: ResolutionResult, confirmed: bool) -> Optional[str]:
        """Handle user confirmation"""
        if confirmed and result.site:
            return result.site
        return None

def main():
    """Main function for testing"""
    resolver = DeterministicResolver()
    
    # Test cases
    test_cases = [
        "gmail",
        "google mail",
        "face book",
        "amazon dot com",
        "you tube",
        "net flix",
        "pay pal",
        "e bay",
        "spot i fy",
        "insta gram"
    ]
    
    print("Deterministic Resolver Test")
    print("=" * 40)
    
    for test_case in test_cases:
        result = resolver.resolve_site(test_case)
        print(f"Input: '{test_case}'")
        print(f"  Site: {result.site}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Method: {result.method}")
        print(f"  Needs Confirmation: {result.needs_confirmation}")
        print()
    
    # Show catalog stats
    stats = resolver.get_catalog_stats()
    print(f"Catalog Stats: {stats['total_sites']} sites, {stats['total_aliases']} aliases")

if __name__ == "__main__":
    main()
