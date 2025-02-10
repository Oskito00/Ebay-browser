CONDITION_IDS = {
    'new': '1000',
    'refurbished': '2000',
    'used': '3000',
    'open_box': '1500',
    'seller_refurbished': '2500'
}

MARKETPLACE_IDS = {
    'EBAY_GB': {
        'code': 'EBAY_GB',
        'location': 'GB',
        'country': 'United Kingdom',
        'site': 'ebay.co.uk',
        'currency': 'GBP',
    },
    'EBAY_US': {
        'code': 'EBAY_US',
        'location': 'US',
        'country': 'United States',
        'site': 'ebay.com',
        'currency': 'USD',
    },
    'EBAY_DE': {
        'code': 'EBAY_DE',
        'location': 'DE',
        'country': 'Germany',
        'site': 'ebay.de',
        'currency': 'EUR',
    },
    'EBAY_CA': {
        'code': 'EBAY_CA',
        'location': 'CA',
        'country': 'Canada',
        'site': 'ebay.ca',
        'currency': 'CAD',
    },
    'EBAY_AU': {
        'code': 'EBAY_AU',
        'location': 'AU',
        'country': 'Australia',
        'site': 'ebay.com.au',
        'currency': 'AUD',
    },
    'EBAY_FR': {
        'code': 'EBAY_FR',
        'location': 'FR',
        'country': 'France',
        'site': 'ebay.fr',
        'currency': 'EUR',
    },
    'EBAY_IT': {
        'code': 'EBAY_IT',
        'location': 'IT',
        'country': 'Italy',
        'site': 'ebay.it',
        'currency': 'EUR',
    },
    'EBAY_ES': {
        'code': 'EBAY_ES',
        'location': 'ES',
        'country': 'Spain',
        'site': 'ebay.es',
        'currency': 'EUR',
    },
    'EBAY_NL': {
        'code': 'EBAY_NL',
        'location': 'NL',
        'country': 'Netherlands',
        'site': 'ebay.nl',
        'currency': 'EUR',
    },
    'EBAY_PL': {
        'code': 'EBAY_PL',
        'location': 'PL',
        'country': 'Poland',
        'site': 'ebay.pl',
        'currency': 'EUR',
    }
}

__all__ = ['CONDITION_IDS', 'MARKETPLACE_IDS']  # Explicit exports 