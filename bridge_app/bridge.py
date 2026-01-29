import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from kafka import KafkaConsumer, KafkaProducer
import json
import threading
import sys

# Force unbuffered output
def log(msg):
    print(msg, flush=True)
    sys.stdout.flush()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- 1. NEW: Kafka Producer for UI -> Kafka ---
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    value_serializer=lambda x: json.dumps(x).encode('utf-8'),
    # Optimization for low latency
    acks=1,
    linger_ms=0 
)

@app.route('/')
def index():
    return render_template('index.html')

# --- 2. NEW: Route to receive data from UI ---
@app.route('/send', methods=['POST'])
def send_to_kafka():
    try:
        data = request.json
        log(f"UI sent data: {data}")
        
        # Send to the topic Spark is listening to
        producer.send('raw-events', value=data)
        
        # 3. THE FIX: Flush forces the message out NOW instead of buffering
        producer.flush() 
        
        return jsonify({"status": "success", "message": "Sent to Kafka"}), 200
    except Exception as e:
        log(f"PRODUCER ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def kafka_listener():
    log("Checking Kafka connection (Consumer)...")
    # Added a retry loop here so it doesn't crash if Kafka is slow to boot
    consumer = None
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                'processed-events',
                bootstrap_servers=['kafka:9092'],
                auto_offset_reset='latest', # Changed to latest to avoid old data flood
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
        except Exception as e:
            log(f"Kafka not ready, retrying in 2s... {e}")
            import time
            time.sleep(2)

    log("Successfully connected to Kafka topic: processed-events")
    for message in consumer:
        data = message.value
        log(f"Bridge received from Spark: {data}")
        socketio.emit('new_result', data)

if __name__ == '__main__':
    log("Starting Bridge App on port 5005...")
    threading.Thread(target=kafka_listener, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5005, allow_unsafe_werkzeug=True)