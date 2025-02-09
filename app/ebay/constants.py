CONDITION_IDS = {
    'new': '1000',
    'refurbished': '2000',
    'used': '3000',
    'open_box': '1500',
    'seller_refurbished': '2500'
}

MARKETPLACE_IDS = {
    'EBAY_GB': {'currency': 'GBP', 'country': 'UK'},
    'EBAY_US': {'currency': 'USD', 'country': 'US'},
    'EBAY_DE': {'currency': 'EUR', 'country': 'DE'},
    'EBAY_IT': {'currency': 'EUR', 'country': 'IT'},
    'EBAY_AU': {'currency': 'AUD', 'country': 'AU'}
}

__all__ = ['CONDITION_IDS', 'MARKETPLACE_IDS']  # Explicit exports 