from flask import Flask, render_template, request, jsonify
from ebay_monitor_browse import EbayMonitor
import threading
import os
from dotenv import load_dotenv

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
    
    if monitor_thread and monitor_thread.is_alive():
        return jsonify({'status': 'error', 'message': 'Monitor already running'})
    
    stop_flag = False
    monitor = EbayMonitor()
    
    # Clear known items when starting a new search
    monitor.known_items = set()
    monitor.save_known_items()
    
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
    global monitor_thread, stop_flag
    if monitor_thread and monitor_thread.is_alive():
        stop_flag = True
        monitor_thread = None
        return jsonify({'status': 'success', 'message': 'Monitor stopped'})
    return jsonify({'status': 'error', 'message': 'No monitor running'})

if __name__ == '__main__':
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
        
    app.run(host='0.0.0.0', port=5001, debug=True) 