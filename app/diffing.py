import re
import hashlib
from typing import Dict, Any, List, Tuple


class DOMDiffEngine:
    """
    Structural & Semantic DOM Diffing Engine.
    Filters dynamic boilerplate, CSRF tokens, and timestamps to isolate meaningful business changes.
    """

    @staticmethod
    def sanitize_html(html_content: str) -> str:
        """
        Strips dynamic script tags, styles, SVG paths, CSRF tokens, and boilerplate footer years.
        """
        if not html_content:
            return ""

        # Remove script and style tags
        text = re.sub(r'<script.*?>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style.*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        
        # Remove CSRF tokens, nonces, timestamps
        text = re.sub(r'csrf[-_]?token=["\'][^"\']+["\']', '', text, flags=re.IGNORECASE)
        text = re.sub(r'nonce=["\'][^"\']+["\']', '', text, flags=re.IGNORECASE)
        text = re.sub(r'©\s*\d{4}', '© YEAR', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def compute_ast_hash(content: str) -> str:
        """
        Computes SHA-256 structural content hash.
        """
        clean_text = DOMDiffEngine.sanitize_html(content)
        return hashlib.sha256(clean_text.encode('utf-8')).hexdigest()

    @staticmethod
    def extract_semantic_changes(old_html: str, new_html: str) -> Tuple[bool, List[str], float]:
        """
        Compares old vs new HTML versions.
        Returns:
        - has_changed: bool
        - detected_deltas: List[str]
        - diff_magnitude: float (0.0 to 1.0)
        """
        clean_old = DOMDiffEngine.sanitize_html(old_html)
        clean_new = DOMDiffEngine.sanitize_html(new_html)

        if clean_old == clean_new:
            return False, [], 0.0

        old_words = set(clean_old.split())
        new_words = set(clean_new.split())

        added_words = new_words - old_words
        removed_words = old_words - new_words

        deltas = []
        if any(w in added_words for w in ['pricing', 'tier', 'plan', '$', '€', '/month', '/yr', 'enterprise']):
            deltas.append("PRICING_STRUCTURE_MODIFIED")
        if any(w in added_words for w in ['careers', 'hiring', 'positions', 'engineers', 'sales', 'join']):
            deltas.append("CAREERS_SECTION_UPDATED")
        if any(w in added_words for w in ['services', 'integrations', 'solutions', 'api', 'platform']):
            deltas.append("PRODUCT_OFFERING_EXPANDED")

        total_word_count = max(1, len(old_words.union(new_words)))
        diff_magnitude = len(added_words.union(removed_words)) / float(total_word_count)

        return True, deltas, min(1.0, round(diff_magnitude, 4))
