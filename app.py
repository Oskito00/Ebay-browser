from flask import Flask, render_template, request, jsonify
from ebay_monitor_browse import EbayMonitor
import threading
import os
from dotenv import load_dotenv
import argparse

# Load environment variables
load_dotenv()

app = Flask(__name__)
monitor = None
monitor_thread = None
stop_flag = False

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_monitor():
    global monitor, monitor_thread, stop_flag
    
    data = request.json
    search_term = data.get('search_term', 'iPhone 14 Pro')
    check_interval = int(data.get('check_interval', 20))
    
    # Get filters
    filters = {}
    if data.get('min_price'):
        filters['min_price'] = float(data['min_price'])
    if data.get('max_price'):
        filters['max_price'] = float(data['max_price'])
    if data.get('condition'):
        filters['condition'] = data['condition']
    if data.get('required_keywords'):
        filters['required_keywords'] = data['required_keywords']
    
    if monitor_thread and monitor_thread.is_alive():
        return jsonify({'status': 'error', 'message': 'Monitor already running'})
    
    stop_flag = False
    monitor = EbayMonitor(instance_name=args.instance_name)
    
    # Reset known items and item details
    monitor.known_items = set()
    monitor.item_details = {}
    monitor.save_known_items()
    monitor.save_item_details()
    
    monitor_thread = threading.Thread(
        target=monitor.monitor,
        args=(search_term, check_interval),
        kwargs={'filters': filters}
    )
    monitor_thread.daemon = True
    monitor_thread.start()
    
    return jsonify({
        'status': 'success',
        'message': f'Monitor started for {search_term}'
    })

@app.route('/stop', methods=['POST'])
def stop_monitor():
    global monitor_thread, stop_flag, monitor
    if monitor_thread and monitor_thread.is_alive():
        stop_flag = True
        # Clear known items and item details when stopping
        if monitor:
            monitor.known_items = set()
            monitor.item_details = {}
            monitor.save_known_items()
            monitor.save_item_details()
        monitor_thread = None
        return jsonify({'status': 'success', 'message': 'Monitor stopped and reset'})
    return jsonify({'status': 'error', 'message': 'No monitor running'})

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