from flask import current_app
from app.ebay.api import EbayAPI

def create_ebay_client():
    # Reuse existing client if possible
    if not hasattr(current_app, 'ebay_client'):
        current_app.ebay_client = EbayAPI()
    return current_app.ebay_client

def scrape_ebay(keywords, filters=None, marketplace='EBAY_GB'):
    # Ensure running within app context
    with current_app.app_context():
        api = create_ebay_client()
        return api.search_all_pages(
            keywords=keywords,
            filters=filters,
            marketplace=marketplace
        )
    
def scrape_new_items(keywords, filters=None, marketplace='EBAY_GB'):
    # Ensure running within app context
    with current_app.app_context():
        api = create_ebay_client()
        return api.search_new_items(
            keywords=keywords,
            filters=filters,
            marketplace=marketplace
                            )
