import re
import unicodedata

def preprocess_text(text: str) -> str:
    """
    Enhanced text normalization:
    - Converts to ASCII (handles accented characters)
    - Standardizes special characters
    - Normalizes unicode variations
    """
    # Convert to ASCII and normalize unicode
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Standardize common characters
    text = re.sub(r'[©®™]', '', text)  # Remove common trademark symbols
    text = re.sub(r'&', ' and ', text)  # Replace ampersands
    
    # Handle special cases
    text = re.sub(r"['']", '', text)    # Remove apostrophes
    text = re.sub(r'[-_]', ' ', text)   # Treat hyphens/underscores as spaces
    
    # Normalize remaining characters
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove remaining punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Handle number normalization (e.g., "1st" -> "1 st")
    text = re.sub(r'(\d+)([a-zA-Z]+)', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z]+)(\d+)', r'\1 \2', text)
    
    return text

def normalize_special_terms(text: str) -> str:
    """Handle common substitutions for better matching"""
    substitutions = {
        r'\biii\b': '3',
        r'\bii\b': '2',
        r'\biv\b': '4',
        r'\bvs\b': 'versus',
        r'\bft\b': 'feet',
        r'\bpokemon\b': 'pokémon',  # Standardize spelling
    }
    
    for pattern, replacement in substitutions.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def get_exact_match_score(query: str, item_text: str) -> float:
    """Enhanced with term normalization"""
    query = normalize_special_terms(preprocess_text(query))
    item = normalize_special_terms(preprocess_text(item_text))
    
    query_words = set(query.split())
    item_words = set(item.split())
    
    if not query_words:
        return 0.0
    
    # Allow partial matches for numbers
    number_matches = sum(
        1 for q in query_words if q.isdigit() and any(i.startswith(q) for i in item_words)
    )
    
    exact_matches = len(query_words & item_words) + number_matches
    return min(exact_matches / len(query_words), 1.0)

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates minimum single-character edits (insert, delete, substitute)
    needed to change s1 into s2
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def normalized_levenshtein_similarity(query: str, item_text: str) -> float:
    """Enhanced with special character handling"""
    processed_query = normalize_special_terms(preprocess_text(query))
    processed_item = normalize_special_terms(preprocess_text(item_text))
    
    max_len = max(len(processed_query), len(processed_item))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(processed_query, processed_item)
    return 1.0 - (distance / max_len)

def has_negative_keywords(item_text: str, negative_terms: set) -> float:
    """
    Returns 1.0 if no negative terms present, 0.0 if any found
    """
    item_words = set(preprocess_text(item_text).split())
    return 0.0 if item_words & negative_terms else 1.0

def calculate_relevance_score(
    query: str,
    item_text: str,
) -> float:
    """
    Enhanced scoring with:
    - 60% exact matches (with number handling)
    - 40% normalized levenshtein
    """
    exact_score = get_exact_match_score(query, item_text)
    lev_score = normalized_levenshtein_similarity(query, item_text)
    
    return (
        (exact_score * 0.6) +
        (lev_score * 0.4)
    )
