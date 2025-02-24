from flask import current_app
from app.ebay.api import EbayAPI

def create_ebay_client():
    # Reuse existing client if possible
    if not hasattr(current_app, 'ebay_client'):
        current_app.ebay_client = EbayAPI()
    return current_app.ebay_client

def scrape_ebay(keywords, filters=None, marketplace='EBAY_GB', required_keywords=None, excluded_keywords=None):
    # Ensure running within app context
    with current_app.app_context():
        api = create_ebay_client()
        return api.custom_search_query(
            keywords=keywords,
            filters=filters,
            sort_order='newlyListed',
            max_pages=4, #TODO: Change to None when ready
            marketplace=marketplace,
            required_keywords=required_keywords,
            excluded_keywords=excluded_keywords
        )
    
def scrape_new_items(keywords, filters=None, marketplace='EBAY_GB', required_keywords=None, excluded_keywords=None):
    # Ensure running within app context
    with current_app.app_context():
        api = create_ebay_client()
        return api.custom_search_query(
            keywords=keywords,
            filters=filters,
            sort_order='newlyListed',
            max_pages=1,
            marketplace=marketplace,
            required_keywords=required_keywords,
            excluded_keywords=excluded_keywords
        )