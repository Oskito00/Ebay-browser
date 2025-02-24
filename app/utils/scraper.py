from flask import current_app
from app.ebay.api import EbayAPI
from threading import local
from circuitbreaker import circuit

_thread_local = local()

def create_ebay_client():
    if not hasattr(_thread_local, 'ebay_client'):
        _thread_local.ebay_client = EbayAPI()
    return _thread_local.ebay_client

@circuit(
    failure_threshold=3, 
    recovery_timeout=60
)
def scrape_ebay(keywords, filters=None, marketplace='EBAY_GB', required_keywords=None, excluded_keywords=None):
    api = create_ebay_client()
    return api.custom_search_query(
        keywords=keywords,
        filters=filters,
        sort_order='newlyListed',
        max_pages=2, #TODO: Change to None when ready
        marketplace=marketplace,
        required_keywords=required_keywords,
        excluded_keywords=excluded_keywords
    )
    
def scrape_new_items(keywords, filters=None, marketplace='EBAY_GB', required_keywords=None, excluded_keywords=None):
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