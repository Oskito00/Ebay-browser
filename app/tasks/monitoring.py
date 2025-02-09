from app.ebay.api import EbayAPI
from app.ebay.constants import CONDITIONS
from app.models import Query, Item

def check_query(query_id):
    query = Query.query.get(query_id)
    
    # Convert human-readable conditions to eBay IDs
    ebay_conditions = [CONDITIONS[c] for c in query.filters.get('conditions', [])]
    
    api = EbayAPI()
    results = api.search_items(
        query.keywords,
        filters={
            'min_price': query.filters.get('min_price'),
            'max_price': query.filters.get('max_price'),
            'condition': ebay_conditions
        }
    )
    
    # Process results... 