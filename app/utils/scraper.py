from flask import current_app
from app.ebay.api import EbayAPI

def scrape_ebay(keywords, filters=None, marketplace='EBAY_GB'):
    """Wrapper for your existing EbayAPI"""
    api = EbayAPI(
        client_id=current_app.config['EBAY_CLIENT_ID'],
        client_secret=current_app.config['EBAY_CLIENT_SECRET'],
        marketplace=marketplace
    )
    return api.search_all_pages(keywords, filters)
