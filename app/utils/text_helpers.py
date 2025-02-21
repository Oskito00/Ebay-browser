import re


def filter_items(items, required_keywords, excluded_keywords):
    # Convert None to empty string for safety
    required = required_keywords or ''
    excluded = excluded_keywords or ''
    
    # Normalize inputs
    req_kws = {kw.strip().lower() for kw in required.split(',') if kw.strip()}
    excl_kws = {ekw.strip().lower() for ekw in excluded.split(',') if ekw.strip()}
    
    # Preprocess titles with null handling
    processed = []
    for item in items:
        # Handle null title/description
        title = (item.get('title') or '').lower()
        description = (item.get('description') or '').lower()
        full_text = f"{title} {description}"
        
        # Split into words from both title and description
        words = set(re.findall(r'\w+', full_text))
        processed.append((item, full_text, words))
    
    # Filter logic
    filtered = []
    for item, full_text, words in processed:
        # Required: all keywords present as whole words
        req_ok = all(
            re.search(rf'\b{re.escape(kw)}\b', full_text) 
            for kw in req_kws
        ) if req_kws else True
        
        # Excluded: none present as substrings
        excl_ok = not any(
            ekw in full_text
            for ekw in excl_kws
        ) if excl_kws else True
        
        if req_ok and excl_ok:
            filtered.append(item)
    
    return filtered