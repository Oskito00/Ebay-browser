import os
import time
from dotenv import load_dotenv
from app.ebay.api import EbayAPI

load_dotenv()  # Load .env file

def live_search_test():
    api = EbayAPI()
    
    # Test Case 1: Basic Search
    print("\nTest 1: Basic Search (iphone)")
    result1 = api.search("iphone", limit=5)
    print(f"Found {result1['total']} items")
    for item in result1['itemSummaries'][:3]:
        print(f" - {item['title']} (${item['price']['value']})")
    
    # Test Case 2: Price Filter
    print("\nTest 2: Price Filter (min £100)")
    result2 = api.search("camera", {'min_price': 100}, limit=5)
    prices = [float(item['price']['value']) for item in result2['itemSummaries']]
    print(f"Prices: {prices}")
    assert all(p >= 100 for p in prices), "Price filter failed"
    
    # Test Case 3: Pagination
    print("\nTest 3: Pagination (offset 10)")
    result3 = api.search("laptop", limit=5, offset=10)
    print(f"Items 11-15: {len(result3['itemSummaries'])} items")
    
    # Test Case 4: Rate Limit Handling
    print("\nTest 4: Rate Limit Check (3 rapid requests)")
    for i in range(3):
        start = time.time()
        api.search("test", limit=1)
        print(f"Request {i+1} took {time.time()-start:.2f}s")

if __name__ == "__main__":
    live_search_test()