from flask import Flask, render_template, request, jsonify
from ebay_monitor_browse import EbayMonitor
import threading
import os
from dotenv import load_dotenv
import argparse
import json
import hashlib
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
monitor = EbayMonitor()  # Initialize on app start
monitor_thread = None
stop_flag = False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/queries', methods=['POST'])
def manage_queries():
    data = request.json
    action = data.get('action')
    
    if action == 'add':
        query_data = data['query']
        query_id = str(uuid.uuid4())
        
        # Convert empty strings to None for prices
        filters = {
            'required_keywords': query_data.get('filters', {}).get('required_keywords', []),
            'exclude_keywords': query_data.get('filters', {}).get('exclude_keywords', []),
            'min_price': query_data.get('filters', {}).get('min_price') or None,
            'max_price': query_data.get('filters', {}).get('max_price') or None,
            'condition': query_data.get('filters', {}).get('condition') or None
        }
        
        monitor.add_query(
            query_id=query_id,
            keywords=query_data['keywords'],
            filters={k: v for k, v in filters.items() if v is not None}
        )
        
        return jsonify({'status': 'success', 'query_id': query_id})
    
    elif action == 'remove':
        query_id = data.get('query_id')
        if not query_id:
            return jsonify({'status': 'error', 'message': 'Missing query_id'}), 400
            
        monitor.remove_query(query_id)
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'error'})

@app.route('/control', methods=['POST'])
def control_monitor():
    action = request.json.get('action')
    
    if action == 'start':
        monitor.active = True
    elif action == 'stop':
        monitor.active = False
    else:
        return jsonify({'status': 'error'}), 400
    
    monitor._save_queries()  # Ensure state persists
    return jsonify({'status': 'success', 'active': monitor.active})

@app.route('/queries', methods=['GET'])
def get_queries():
    return jsonify({
        'queries': monitor.queries,
        'active': monitor.active
    })

if __name__ == '__main__':
    # Setup argument parser
    parser = argparse.ArgumentParser(description='eBay Monitor')
    parser.add_argument('--port', type=int, default=5001,
                      help='Port number (default: 5001)')
    parser.add_argument('--telegram-token', type=str,
                      help='Telegram Bot Token')
    parser.add_argument('--telegram-chat', type=str,
                      help='Telegram Chat ID')
    parser.add_argument('--instance-name', type=str, default="default",
                      help='Unique instance name for separate file storage')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Override with command line arguments if provided
    if args.telegram_token:
        os.environ['TELEGRAM_BOT_TOKEN'] = args.telegram_token
    if args.telegram_chat:
        os.environ['TELEGRAM_CHAT_ID'] = args.telegram_chat

    required_vars = [
        'EBAY_CLIENT_ID', 
        'EBAY_CLIENT_SECRET',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        exit(1)
    
    port = args.port
    app.run(host='0.0.0.0', port=port, debug=True)