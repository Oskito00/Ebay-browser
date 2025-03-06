CONDITION_IDS = {
    'new': '1000',
    'refurbished': '2000',
    'used': '3000',
    'open_box': '1500',
    'seller_refurbished': '2500'
}

TIER_LIMITS = {
    'free': 0,
    'individual': 1500,
    'business': 4000
}

PRICE_TIER_MAPPINGS= {
    "price_1QyckCQ33R4TD00yBV26aiFs": {'name': 'individual', 'query_limit': 1500},
    "price_1QzGoxQ33R4TD00yGBszzKw9": {'name': 'business', 'query_limit': 4000},
}

MARKETPLACE_IDS = {
    'EBAY_GB': {
        'code': 'EBAY_GB',
        'location': 'GB',
        'country': 'United Kingdom',
        'site': 'ebay.co.uk',
        'currency': 'GBP',
        'language': 'en-GB'
    },
    'EBAY_US': {
        'code': 'EBAY_US',
        'location': 'US',
        'country': 'United States',
        'site': 'ebay.com',
        'currency': 'USD',
        'language': 'en-US'
    },
    'EBAY_DE': {
        'code': 'EBAY_DE',
        'location': 'DE',
        'country': 'Germany',
        'site': 'ebay.de',
        'currency': 'EUR',
        'language': 'de-DE'
    },
    'EBAY_CA': {
        'code': 'EBAY_CA',
        'location': 'CA',
        'country': 'Canada',
        'site': 'ebay.ca',
        'currency': 'CAD',
        'language': 'en-CA'  # English Canada
    },
    'EBAY_AU': {
        'code': 'EBAY_AU',
        'location': 'AU',
        'country': 'Australia',
        'site': 'ebay.com.au',
        'currency': 'AUD',
        'language': 'en-AU'  # English Australia
    },
    'EBAY_FR': {
        'code': 'EBAY_FR',
        'location': 'FR',
        'country': 'France',
        'site': 'ebay.fr',
        'currency': 'EUR',
        'language': 'fr-FR'
    },
    'EBAY_IT': {
        'code': 'EBAY_IT',
        'location': 'IT',
        'country': 'Italy',
        'site': 'ebay.it',
        'currency': 'EUR',
        'language': 'it-IT'
    },
    'EBAY_ES': {
        'code': 'EBAY_ES',
        'location': 'ES',
        'country': 'Spain',
        'site': 'ebay.es',
        'currency': 'EUR',
        'language': 'es-ES'
    },
    'EBAY_NL': {
        'code': 'EBAY_NL',
        'location': 'NL',
        'country': 'Netherlands',
        'site': 'ebay.nl',
        'currency': 'EUR',
        'language': 'nl-NL'
    },
    'EBAY_PL': {
        'code': 'EBAY_PL',
        'location': 'PL',
        'country': 'Poland',
        'site': 'ebay.pl',
        'currency': 'PLN',
        'language': 'pl-PL'
    }
}

__all__ = ['CONDITION_IDS', 'MARKETPLACE_IDS']  # Explicit exports 