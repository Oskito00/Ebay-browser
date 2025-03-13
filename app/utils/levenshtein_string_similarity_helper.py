import re

def preprocess_text(text: str) -> str:
    """
    Normalizes text for comparison:
    - Lowercases
    - Removes punctuation
    - Trims whitespace
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text

def get_exact_match_score(query: str, item_text: str) -> float:
    """
    Calculates percentage of query words that exactly match item text
    """
    query_words = set(preprocess_text(query).split())
    item_words = set(preprocess_text(item_text).split())
    
    if not query_words:
        return 0.0
    
    matches = query_words & item_words
    return len(matches) / len(query_words)

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
    """
    Returns similarity score between 0-1 based on edit distance,
    normalized by input lengths
    """
    max_len = max(len(query), len(item_text))
    if max_len == 0:
        return 1.0
    
    distance = levenshtein_distance(
        preprocess_text(query),
        preprocess_text(item_text)
    )
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
    Combines all metrics into a final relevance score (0-1)
    using the hybrid approach
    """
    exact_score = get_exact_match_score(query, item_text)
    lev_score = normalized_levenshtein_similarity(query, item_text)
    
    return (
        (exact_score * 0.5) +
        (lev_score * 0.5)
    )
