import pytest
from unittest.mock import Mock, patch
from app.ebay.api import EbayAPI

@pytest.fixture
def mock_api():
    return EbayAPI(marketplace='EBAY_GB')  # Default to UK

def test_german_marketplace():
    api = EbayAPI(marketplace='EBAY_DE')
    
    with patch('requests.get') as mock_get:
        mock_response = {
            'itemSummaries': [
                {
                    'title': 'Test Item',
                    'price': {'value': '100.00', 'currency': 'EUR'},
                    'itemLocation': {'country': 'DE'}
                }
            ],
            'total': 1
        }
        mock_get.return_value.json.return_value = mock_response
        
        results = api.search("test", {'item_location': 'DE'})
        
        # Check items array length
        assert len(results['itemSummaries']) == 1
        # Check total count
        assert results['total'] == 1


@pytest.mark.parametrize("marketplace,expected_currency,expected_country", [
    ('EBAY_GB', 'GBP', 'GB'),
    ('EBAY_DE', 'EUR', 'DE'),
    ('EBAY_US', 'USD', 'US'),
])
def test_marketplace_filtering(marketplace, expected_currency, expected_country):
    api = EbayAPI(marketplace=marketplace)
    filters = {'item_location': expected_country}
    
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {'itemSummaries': [{}]}
        
        api.search("test", filters)
        
        request = mock_get.call_args[1]['params']
        assert f"itemLocationCountry:{expected_country}" in request['filter']
        assert f"currency:{expected_currency}" in request['filter']



# def test_live_german_search():
#     api = EbayAPI(marketplace='EBAY_DE')
#     results = api.search("kamera", {'item_location': 'DE'})
    
#     assert len(results) > 0
#     for item in results:
#         assert item['currency'] == 'EUR'
#         assert item['country'] == 'DE'
