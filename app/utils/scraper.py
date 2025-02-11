from flask import current_app
from app.ebay.api import EbayAPI

def create_ebay_client():
    return EbayAPI()

def scrape_ebay(keywords, filters=None, marketplace='EBAY_GB'):
    # Ensure running within app context
    with current_app.app_context():
        api = create_ebay_client()
        return api.search_all_pages(
            keywords=keywords,
            filters=filters,
            marketplace=marketplace
        )
