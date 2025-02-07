import pytest
from unittest.mock import Mock, patch
import time
from ebay_monitor.monitor import EbayMonitor
from ebay_monitor.ebay_api import EbayAPI
import os

@pytest.fixture
def monitor():
    mock_api = Mock()
    mock_api.search.return_value = {'itemSummaries': []}
    
    with patch('ebay_monitor.monitor.EbayAPI') as mock_ebay_api:
        mock_ebay_instance = mock_ebay_api.return_value
        mock_ebay_instance.search = mock_api.search
        
        monitor = EbayMonitor(api=mock_ebay_instance)
        yield monitor
        # Cleanup
        monitor.active = False
        if monitor.monitor_thread and monitor.monitor_thread.is_alive():
            monitor.monitor_thread.join(timeout=1)
        # Reset data
        monitor.queries.clear()
        monitor.known_items.clear()
        if os.path.exists('queries.json'):
            os.remove('queries.json')

def test_add_query(monitor):
    query_id = "test123"
    monitor.add_query(query_id, "test keywords", {'marketplace': 'EBAY-GB'})
    
    # Monitoring not started yet
    assert query_id in monitor.queries
    assert query_id in monitor.known_items
    monitor.api.search.assert_not_called()  # Now passes

def test_remove_query(monitor):
    query_id = "test123"
    monitor.add_query(query_id, "test keywords", {})
    monitor.remove_query(query_id)
    assert query_id not in monitor.queries
    assert query_id not in monitor.known_items

def test_first_run(monitor):
    query_id = "test123"
    mock_results = {
        'itemSummaries': [{'itemId': '1'}, {'itemId': '2'}],
        'total': 2
    }
    monitor.api.search.return_value = mock_results
    
    monitor.add_query(query_id, "test", {'marketplace': 'EBAY-GB'})
    monitor.start()
    assert monitor.active is True  # Verify monitoring is active
    
    # Wait for query processing
    monitor.query_processed.wait(timeout=3)  # Wait for event
    
    # Check directly in the queries dict
    with monitor.lock:
        assert not monitor.queries[query_id]['first_run'], \
            f"First run flag still True. Query data: {monitor.queries[query_id]}"
    assert len(monitor.known_items[query_id]) == 2, "Items not recorded"
    monitor.api.search.assert_called_once()  # Verify API called

def test_new_item_detection(monitor):
    query_id = "test123"
    monitor.add_query(query_id, "test", {'marketplace': 'EBAY-GB'})
    monitor.known_items[query_id] = {'1'}
    
    mock_results = {
        'itemSummaries': [{'itemId': '1'}, {'itemId': '2'}],
        'total': 2
    }
    monitor.api.search.return_value = mock_results
    mock_api = monitor.api
    mock_api.search.side_effect = [
        {'itemSummaries': [{'itemId': str(i)} for i in range(100)], 'total': 150},
        {'itemSummaries': [{'itemId': str(i)} for i in range(100, 150)], 'total': 150}
    ]
    
    query_id = "pagination_test"
    monitor.add_query(query_id, "test", {'marketplace': 'EBAY-US'})
    monitor.start()
    
    # Wait for both pages
    max_retries = 10
    for _ in range(max_retries):
        if len(monitor.known_items.get(query_id, [])) >= 150:
            break
        time.sleep(0.5)
    else:
        pytest.fail("Pagination didn't complete")
    
    assert len(monitor.known_items[query_id]) == 150
    assert mock_api.search.call_count == 2
    time.sleep(2)
    
    assert len(monitor.known_items[query_id]) == 150
    assert mock_api.search.call_count == 2 