"""
=============================================================================
 IoT Camera System - Web Server Core
 Phien ban: 2.0 (IoT Protocol)
 Giao thuc: HTTP REST + MQTT + WebSocket
=============================================================================
"""
import sys
import os
# Fix Unicode encoding tren Windows (cho phep print emoji va tieng Viet)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    os.environ['PYTHONIOENCODING'] = 'utf-8'


# ========================= THƯ VIỆN =========================
from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from PIL import Image
import io
import struct
import numpy as np
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import paho.mqtt.client as mqtt
import mysql.connector
import os
import json
import time
import uuid
import threading
import subprocess
import signal
import atexit
from datetime import datetime, timezone

# ========================= CẤU HÌNH =========================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'iot_camera_secret_key_2026'

# Cho phép Cross-Origin (để browser khác domain cũng truy cập được API)
CORS(app)

# Khởi tạo WebSocket server (Flask-SocketIO)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Thư mục lưu ảnh
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Cấu hình MQTT Broker (Chế độ Toàn Cầu)
MQTT_BROKER_HOST = 'broker.emqx.io'
MQTT_BROKER_PORT = 1883
MQTT_USERNAME = ''  
MQTT_PASSWORD = ''
MQTT_CLIENT_ID = 'web_server_minh_hust_camera_2026'

# Cấu hình Heartbeat
HEARTBEAT_TIMEOUT = 8  # Giây — nếu thiết bị không gửi heartbeat trong 8s → offline
HEARTBEAT_CHECK_INTERVAL = 2  # Kiểm tra mỗi 2 giây

# Thời gian server khởi động (để tính uptime)
SERVER_START_TIME = time.time()

# Luu trang thai thiet bi trong bo nho (nhanh hon query# --- Global State ---
device_status_cache = {}  # { device_id: { status, last_seen, ip, ... } }
sim_processes = {}

# ========================= LIVE STREAM STATE =========================
# Lưu frame JPEG mới nhất từ Camera Node để stream lên Dashboard
latest_frame_jpeg = None
latest_frame_lock = threading.Lock()
latest_frame_time = 0
stream_frame_count = 0
SIM_SCRIPTS = {
    'camera': 'sim_camera.py',
    'display': 'sim_display.py'
}
SERVER_START_TIME = time.time()
UPLOAD_STATS = []  # List of (timestamp, bytes) for bandwidth tracking


def clean_upload_stats():
    """Xóa các bản ghi traffic cũ hơn 60 giây."""
    global UPLOAD_STATS
    now = time.time()
    UPLOAD_STATS = [s for s in UPLOAD_STATS if now - s[0] < 60]


def get_current_bandwidth_kbps():
    """Tính toán băng thông tải lên trung bình trong 10 giây qua."""
    now = time.time()
    recent_stats = [s[1] for s in UPLOAD_STATS if now - s[0] < 10]
    if not recent_stats:
        return 0
    total_bytes = sum(recent_stats)
    # Trung bình per second (KB/s)
    return round((total_bytes / 1024) / 10, 2)


# Quan ly cac process simulator
# ========================= DATABASE (MySQL) =========================

# Cau hinh ket noi MySQL Server
MYSQL_CONFIG = {
    'host': '192.168.1.121',
    'port': 3306,
    'user': 'minhmoon2k5',
    'password': 'minhmoon2k5',
    'database': 'iot_camera_db',
    'autocommit': False,
}

def get_db():
    """Tao ket noi den MySQL Server cho moi request/thread."""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    return conn


def init_db():
    """Kiem tra ket noi MySQL va dam bao database da san sang."""
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('SELECT 1')
        conn.close()
        print("[DB] \u2705 Ket noi MySQL Server thanh cong!")
        print(f"[DB] Database: {MYSQL_CONFIG['database']} @ {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}")
    except Exception as e:
        print(f"[DB] \u274c Loi ket noi MySQL: {e}")
        print("[DB] Hay dam bao MySQL Server dang chay va database 'iot_camera_db' da duoc tao!")
        sys.exit(1)


def load_devices_from_db():
    """Load trang thai thiet bi tu DB vao RAM cache khi server khoi dong."""
    global device_status_cache
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('SELECT * FROM devices')
        rows = lenh_db.fetchall()
        conn.close()

        for row in rows:
            device_status_cache[row['device_id']] = {
                'device_id': row['device_id'],
                'device_type': row['device_type'],
                'ip_address': row['ip_address'] or '',
                'status': 'offline',  # Mac dinh offline khi server moi khoi dong
                'last_seen': str(row['last_seen']) if row['last_seen'] else '',
                'wifi_rssi': row['wifi_rssi'] or 0,
                'free_heap': row['free_heap'] or 0,
                'total_uploads': row['total_uploads'] or 0
            }

        if rows:
            print(f"[DB] Da load {len(rows)} thiet bi tu database vao cache")
        else:
            print(f"[DB] Chua co thiet bi nao trong database")
    except Exception as e:
        print(f"[DB] Loi load devices: {e}")


# ========================= MQTT CLIENT =========================

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
mqtt_connected = False  # Biến theo dõi trạng thái kết nối MQTT


def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    """Callback khi kết nối thành công đến MQTT Broker."""
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print("[MQTT] ✅ Đã kết nối đến MQTT Broker!")
        # Subscribe vào các topic cần lắng nghe
        topics = [
            ('iot/camera/ack', 1),       # Camera xác nhận lệnh
            ('iot/camera/status', 1),    # Camera báo trạng thái
            ('iot/display/status', 1),   # Display báo trạng thái
            ('iot/system/heartbeat', 0), # Nhịp tim từ tất cả thiết bị
            ('iot/system/log', 0),       # Log sự kiện
            ('iot/notify/new_image', 1), # Thông báo ảnh mới (để forward lên WebSocket)
        ]
        for topic, qos in topics:
            client.subscribe(topic, qos)
            print(f"  → Subscribed: {topic} (QoS {qos})")
        # Thông báo dashboard MQTT đã kết nối
        socketio.emit('mqtt_status', {'connected': True})
    else:
        mqtt_connected = False
        rc_messages = {
            1: 'Phiên bản protocol không hợp lệ',
            2: 'Client ID bị từ chối',
            3: 'Server không khả dụng',
            4: 'Sai username/password',
            5: 'Không có quyền truy cập'
        }
        reason = rc_messages.get(rc, f'Mã lỗi không xác định: {rc}')
        print(f"[MQTT] ❌ Kết nối thất bại: {reason}")


def on_mqtt_disconnect(client, userdata, flags, rc, properties=None):
    """Callback khi mất kết nối MQTT — paho-mqtt sẽ tự động reconnect."""
    global mqtt_connected
    mqtt_connected = False
    if rc == 0:
        print("[MQTT] ⚠️ Ngắt kết nối (chủ động)")
    else:
        print(f"[MQTT] ⚠️ Mất kết nối! (rc={rc}) — Đang tự động reconnect...")
    socketio.emit('mqtt_status', {'connected': False})


def on_mqtt_message(client, userdata, msg):
    """Callback khi nhận được message từ bất kỳ topic nào đã subscribe."""
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
    except json.JSONDecodeError:
        print(f"[MQTT] ⚠️ Payload không phải JSON: {msg.payload}")
        return

    print(f"[MQTT] 📩 Topic: {topic} | Payload: {json.dumps(payload, ensure_ascii=False)[:200]}")

    # ----- Xử lý theo từng topic -----
    if topic == 'iot/system/heartbeat':
        handle_heartbeat(payload)

    elif topic == 'iot/camera/ack':
        handle_command_ack(payload)

    elif topic == 'iot/system/log':
        handle_device_log(payload)

    elif topic == 'iot/notify/new_image':
        # Server đã tự phát WebSocket khi nhận request upload, nên không cần forward lại từ MQTT
        pass

    elif topic in ('iot/camera/status', 'iot/display/status'):
        handle_device_status(payload)


def handle_heartbeat(payload):
    """Xử lý heartbeat từ thiết bị → cập nhật trạng thái online."""
    device_id = payload.get('device_id', 'UNKNOWN')
    device_type = payload.get('device_type', 'unknown')
    ip_address = payload.get('ip_address', '')
    wifi_rssi = payload.get('wifi_rssi', 0)
    free_heap = payload.get('free_heap', 0)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Cập nhật cache trong bộ nhớ
    status = payload.get('status', 'online')
    existing_info = device_status_cache.get(device_id, {})
    old_status = existing_info.get('status', 'offline')
    
    device_status_cache[device_id] = {
        **existing_info,
        'device_id': device_id,
        'device_type': device_type,
        'status': status,
        'ip_address': ip_address,
        'wifi_rssi': wifi_rssi,
        'free_heap': free_heap,
        'last_seen': now
    }

    # Cập nhật vào database
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('''
            INSERT INTO devices (device_id, device_type, ip_address, status, last_seen, wifi_rssi, free_heap)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                ip_address = VALUES(ip_address),
                status = VALUES(status),
                last_seen = VALUES(last_seen),
                wifi_rssi = VALUES(wifi_rssi),
                free_heap = VALUES(free_heap)
        ''', (device_id, device_type, ip_address, status, now, wifi_rssi, free_heap))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] ⚠️ Lỗi lưu heartbeat: {e}")

    # Nếu thiết bị vừa chuyển từ offline → online, thông báo
    if old_status == 'offline' and status == 'online':
        print(f"[HEARTBEAT] 🟢 {device_id} đã Online!")
    elif status == 'offline':
        print(f"[HEARTBEAT] 🔴 {device_id} đã Offline (LWT)!")

    # Gửi WebSocket cập nhật trạng thái cho browser
    socketio.emit('device_update', device_status_cache[device_id])


def handle_command_ack(payload):
    """Xử lý ACK từ Camera khi nhận xong lệnh."""
    cmd_id = payload.get('cmd_id', '')
    status = payload.get('status', 'UNKNOWN')
    message = payload.get('message', '')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"[ACK] Lệnh {cmd_id}: {status} - {message}")

    # Cập nhật trạng thái lệnh trong database
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('''
            UPDATE commands SET status = %s, ack_at = %s, ack_message = %s
            WHERE cmd_id = %s
        ''', (status, now, message, cmd_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] ⚠️ Lỗi cập nhật ACK: {e}")

    # Forward kết quả lên Dashboard qua WebSocket
    socketio.emit('command_result', {
        'cmd_id': cmd_id,
        'status': status,
        'message': message
    })


def handle_device_log(payload):
    """Lưu log sự kiện từ thiết bị vào database."""
    device_id = payload.get('device_id', 'UNKNOWN')
    level = payload.get('level', 'INFO')
    event = payload.get('event', '')
    message = payload.get('message', '')

    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('''
            INSERT INTO event_logs (device_id, level, event, message)
            VALUES (%s, %s, %s, %s)
        ''', (device_id, level, event, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB] ⚠️ Lỗi lưu log: {e}")

    # Forward log lên Dashboard
    socketio.emit('log_entry', {
        'device_id': device_id,
        'level': level,
        'event': event,
        'message': message,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


def handle_device_status(payload):
    """Xử lý thông báo thay đổi trạng thái từ thiết bị."""
    device_id = payload.get('device_id', 'UNKNOWN')
    status = payload.get('status', 'unknown')

    if device_id in device_status_cache:
        device_status_cache[device_id]['status'] = status

    socketio.emit('device_update', {
        'device_id': device_id,
        'status': status
    })


def setup_mqtt():
    """Khởi tạo và kết nối MQTT Client với auto-reconnect."""
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message

    # Cấu hình bảo mật nếu có username/password (dùng cho Cloud Broker)
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    # Nếu dùng cổng 8883 (TLS/SSL - HiveMQ quy định)
    if MQTT_BROKER_PORT == 8883:
        mqtt_client.tls_set()

    # Cấu hình auto-reconnect (min 1s, max 30s)
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)

    print(f"[MQTT] Đang kết nối đến {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
    try:
        # Dùng connect_async để không block server khi broker chưa sẵn sàng
        mqtt_client.connect_async(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    except Exception as e:
        print(f"[MQTT] ⚠️ Lỗi cấu hình kết nối: {e}")

    # QUAN TRỌNG: Luôn gọi loop_start() dù connect thất bại
    # Để paho-mqtt tự động retry kết nối trong background
    mqtt_client.loop_start()
    print(f"[MQTT] Loop đã khởi động (auto-reconnect: ON)")


# ========================= HEARTBEAT MONITOR =========================

def heartbeat_monitor():
    """
    Background thread: kiểm tra định kỳ xem thiết bị nào đã mất tín hiệu.
    Nếu > HEARTBEAT_TIMEOUT giây không nhận heartbeat → đánh dấu offline.
    """
    while True:
        socketio.sleep(HEARTBEAT_CHECK_INTERVAL)
        now = datetime.now()

        for device_id, info in list(device_status_cache.items()):
            if info['status'] != 'offline':
                try:
                    last_seen = datetime.strptime(info['last_seen'], '%Y-%m-%d %H:%M:%S')
                    elapsed = (now - last_seen).total_seconds()

                    if elapsed > HEARTBEAT_TIMEOUT:
                        # Thiết bị đã offline!
                        device_status_cache[device_id]['status'] = 'offline'
                        print(f"[HEARTBEAT] 🔴 {device_id} đã Offline! (Không có tín hiệu {elapsed:.0f}s)")

                        # Cập nhật DB
                        try:
                            conn = get_db()
                            lenh_db = conn.cursor(dictionary=True)
                            lenh_db.execute(
                                'UPDATE devices SET status = %s WHERE device_id = %s',
                                ('offline', device_id)
                            )
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"[DB] ⚠️ Lỗi cập nhật offline: {e}")

                        # Thông báo Dashboard
                        # Emit cập nhật toàn bộ thông tin
                        socketio.emit('device_update', device_status_cache[device_id])
                except Exception as e:
                    print(f"[HEARTBEAT] ⚠️ Lỗi kiểm tra {device_id}: {e}")


# ========================= HTTP REST API =========================

# ----- API 1: Upload Ảnh (Camera Node → Server) -----
@app.route('/api/upload', methods=['POST'])
def upload_image():
    """
    Camera Node gửi ảnh lên server qua HTTP POST multipart/form-data.
    Sau khi lưu xong:
      1. Ghi metadata vao MySQL
      2. Phát thông báo MQTT lên topic iot/notify/new_image
      3. Emit WebSocket event 'new_image' cho Dashboard
    """
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'error_code': 'NO_IMAGE', 'message': 'No image file in request'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'status': 'error', 'error_code': 'NO_FILENAME', 'message': 'No selected file'}), 400

    # Lấy thông tin bổ sung từ form data
    device_id = request.form.get('device_id', 'WEB_SIMULATOR')
    resolution = request.form.get('resolution', '320x240')

    # Tạo tên file theo thời gian (tránh trùng)
    timestamp = datetime.now()
    unique_filename = timestamp.strftime("%Y%m%d_%H%M%S") + ".jpg"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)

    file_size = os.path.getsize(filepath)

    # Lưu vào database
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute(
            'INSERT INTO images (filename, file_size, device_id, resolution) VALUES (%s, %s, %s, %s)',
            (unique_filename, file_size, device_id, resolution)
        )
        image_id = lenh_db.lastrowid

        # Cập nhật số ảnh đã upload cho thiết bị
        lenh_db.execute('''
            UPDATE devices SET total_uploads = total_uploads + 1
            WHERE device_id = %s
        ''', (device_id,))

        conn.commit()
        conn.close()
    except Exception as e:
        return jsonify({'status': 'error', 'error_code': 'DB_ERROR', 'message': str(e)}), 500

    # Thêm vào thống kê băng thông
    global UPLOAD_STATS
    UPLOAD_STATS.append((time.time(), file_size))
    clean_upload_stats()

    # Dữ liệu ảnh mới
    image_data = {
        'id': image_id,
        'filename': unique_filename,
        'url': f'/uploads/{unique_filename}',
        'file_size': file_size,
        'device_id': device_id,
        'resolution': resolution,
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }

    # Phát MQTT thông báo ảnh mới (cho Display Node và các subscriber khác)
    try:
        mqtt_payload = json.dumps({
            'event': 'NEW_IMAGE',
            'data': image_data
        })
        mqtt_client.publish('iot/notify/new_image', mqtt_payload, qos=1)
        print(f"[MQTT] 📤 Đã phát thông báo ảnh mới: {unique_filename}")
    except Exception as e:
        print(f"[MQTT] ⚠️ Không gửi được thông báo: {e}")

    # Emit WebSocket cho Dashboard (cập nhật real-time)
    socketio.emit('new_image', image_data)
    print(f"[WS] 📤 Đã emit new_image cho Dashboard")

    print(f"[UPLOAD] ✅ {unique_filename} ({file_size} bytes) từ {device_id}")

    return jsonify({
        'status': 'success',
        'message': 'Image uploaded successfully',
        'data': image_data
    }), 201


# ----- API: Nhận Frame RGB565 từ Camera Node (cho Live Stream) -----
@app.route('/api/stream_frame', methods=['POST'])
def receive_stream_frame():
    """
    Camera Node gửi frame RAW RGB565 lên đây.
    Server chuyển RGB565 → JPEG và lưu vào bộ đệm để phát MJPEG stream.
    """
    global latest_frame_jpeg, latest_frame_time, stream_frame_count

    device_id = request.headers.get('X-Device-ID', 'UNKNOWN')
    width = int(request.headers.get('X-Frame-Width', 160))
    height = int(request.headers.get('X-Frame-Height', 120))

    raw_data = request.get_data()
    expected_size = width * height * 2  # RGB565 = 2 bytes/pixel

    if len(raw_data) != expected_size:
        return jsonify({'status': 'error', 'message': f'Expected {expected_size} bytes, got {len(raw_data)}'}), 400

    try:
        # Chuyển RGB565 → RGB888 bằng numpy (nhanh)
        pixels = np.frombuffer(raw_data, dtype=np.uint16)
        # ESP32 gửi little-endian RGB565
        r = ((pixels >> 8) & 0xF8).astype(np.uint8)
        g = ((pixels >> 3) & 0xFC).astype(np.uint8)
        b = ((pixels << 3) & 0xF8).astype(np.uint8)

        rgb = np.stack([r, g, b], axis=-1).reshape(height, width, 3)
        img = Image.fromarray(rgb, 'RGB')

        # Encode sang JPEG
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=75)
        jpeg_bytes = buf.getvalue()

        with latest_frame_lock:
            latest_frame_jpeg = jpeg_bytes
            latest_frame_time = time.time()
            stream_frame_count += 1

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print(f'[STREAM] ❌ Lỗi xử lý frame: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ----- API: Upload Raw Frame thành ảnh JPEG (cho lệnh CAPTURE) -----
@app.route('/api/upload_raw', methods=['POST'])
def upload_raw_frame():
    """
    Camera Node chụp 1 ảnh RAW RGB565 và gửi lên.
    Server chuyển thành JPEG, lưu file, ghi DB, và thông báo Dashboard.
    """
    device_id = request.headers.get('X-Device-ID', 'CAM_NODE_01')
    width = int(request.headers.get('X-Frame-Width', 160))
    height = int(request.headers.get('X-Frame-Height', 120))

    raw_data = request.get_data()
    expected_size = width * height * 2

    if len(raw_data) != expected_size:
        return jsonify({'status': 'error', 'message': f'Size mismatch: {len(raw_data)} vs {expected_size}'}), 400

    try:
        # Chuyển RGB565 → JPEG
        pixels = np.frombuffer(raw_data, dtype=np.uint16)
        r = ((pixels >> 8) & 0xF8).astype(np.uint8)
        g = ((pixels >> 3) & 0xFC).astype(np.uint8)
        b = ((pixels << 3) & 0xF8).astype(np.uint8)
        rgb = np.stack([r, g, b], axis=-1).reshape(height, width, 3)
        img = Image.fromarray(rgb, 'RGB')

        # Lưu file JPEG
        timestamp = datetime.now()
        unique_filename = timestamp.strftime('%Y%m%d_%H%M%S') + '.jpg'
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        img.save(filepath, format='JPEG', quality=85)
        file_size = os.path.getsize(filepath)

        # Lưu vào database
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute(
            'INSERT INTO images (filename, file_size, device_id, resolution) VALUES (%s, %s, %s, %s)',
            (unique_filename, file_size, device_id, f'{width}x{height}')
        )
        image_id = lenh_db.lastrowid
        lenh_db.execute('UPDATE devices SET total_uploads = total_uploads + 1 WHERE device_id = %s', (device_id,))
        conn.commit()
        conn.close()

        # Thống kê
        global UPLOAD_STATS
        UPLOAD_STATS.append((time.time(), file_size))
        clean_upload_stats()

        image_data = {
            'id': image_id,
            'filename': unique_filename,
            'url': f'/uploads/{unique_filename}',
            'file_size': file_size,
            'device_id': device_id,
            'resolution': f'{width}x{height}',
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }

        # Thông báo MQTT + WebSocket
        try:
            mqtt_payload = json.dumps({'event': 'NEW_IMAGE', 'data': image_data})
            mqtt_client.publish('iot/notify/new_image', mqtt_payload, qos=1)
        except Exception as e:
            print(f'[MQTT] ⚠️ Không gửi được thông báo: {e}')

        socketio.emit('new_image', image_data)
        print(f'[CAPTURE] ✅ {unique_filename} ({file_size} bytes) từ {device_id} (RAW→JPEG)')

        return jsonify({'status': 'success', 'data': image_data}), 201

    except Exception as e:
        print(f'[CAPTURE] ❌ Lỗi: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ----- API: MJPEG Video Feed (cho Dashboard xem trực tiếp) -----
@app.route('/api/video_feed')
def video_feed():
    """Trả về MJPEG stream — browser hiển thị bằng <img src=...>."""
    def generate():
        last_sent = 0
        while True:
            with latest_frame_lock:
                frame = latest_frame_jpeg
                frame_time = latest_frame_time

            if frame and frame_time > last_sent:
                last_sent = frame_time
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' +
                       frame + b'\r\n')

            time.sleep(0.05)  # ~20 FPS max polling

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ----- API: Snapshot (1 frame JPEG mới nhất) -----
@app.route('/api/stream/snapshot')
def stream_snapshot():
    """Trả về frame JPEG mới nhất dưới dạng ảnh tĩnh."""
    with latest_frame_lock:
        frame = latest_frame_jpeg

    if frame:
        return Response(frame, mimetype='image/jpeg',
                        headers={'Cache-Control': 'no-cache, no-store, must-revalidate'})
    else:
        # Trả về ảnh placeholder
        img = Image.new('RGB', (160, 120), (26, 29, 39))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        return Response(buf.getvalue(), mimetype='image/jpeg')


# ----- API 2: Lấy Ảnh Mới Nhất -----
@app.route('/api/latest', methods=['GET'])
def get_latest_image():
    """Trả ảnh mới nhất. Hỗ trợ ?format=json để trả metadata."""
    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)
    lenh_db.execute('SELECT * FROM images ORDER BY timestamp DESC LIMIT 1')
    row = lenh_db.fetchone()
    conn.close()

    if not row:
        return jsonify({'status': 'error', 'error_code': 'NO_IMAGES', 'message': 'No images found'}), 404

    # Nếu yêu cầu JSON metadata
    if request.args.get('format') == 'json':
        return jsonify({
            'status': 'success',
            'data': {
                'id': row['id'],
                'filename': row['filename'],
                'url': f'/uploads/{row["filename"]}',
                'file_size': row['file_size'],
                'device_id': row['device_id'],
                'resolution': row['resolution'],
                'timestamp': str(row['timestamp'])
            }
        })

    # Mặc định trả file ảnh binary
    return send_from_directory(UPLOAD_FOLDER, row['filename'])


# ----- API 3: Danh Sách Ảnh (Phân Trang) -----
@app.route('/api/images', methods=['GET'])
def get_images():
    """Trả danh sách ảnh có phân trang."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)

    # Đếm tổng
    lenh_db.execute('SELECT COUNT(*) as total FROM images')
    total = lenh_db.fetchone()['total']

    # Lấy danh sách theo trang
    lenh_db.execute(
        'SELECT * FROM images ORDER BY timestamp DESC LIMIT %s OFFSET %s',
        (per_page, offset)
    )
    rows = lenh_db.fetchall()
    conn.close()

    images = [{
        'id': row['id'],
        'filename': row['filename'],
        'url': f'/uploads/{row["filename"]}',
        'file_size': row['file_size'],
        'device_id': row['device_id'],
        'resolution': row['resolution'],
        'timestamp': str(row['timestamp'])
    } for row in rows]

    return jsonify({
        'status': 'success',
        'data': {
            'images': images,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_images': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        }
    })


# ----- API 4: Chi Tiết 1 Ảnh -----
@app.route('/api/images/<int:image_id>', methods=['GET'])
def get_image_detail(image_id):
    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)
    lenh_db.execute('SELECT * FROM images WHERE id = %s', (image_id,))
    row = lenh_db.fetchone()
    conn.close()

    if not row:
        return jsonify({'status': 'error', 'message': 'Image not found'}), 404

    return jsonify({
        'status': 'success',
        'data': {
            'id': row['id'],
            'filename': row['filename'],
            'url': f'/uploads/{row["filename"]}',
            'file_size': row['file_size'],
            'device_id': row['device_id'],
            'resolution': row['resolution'],
            'timestamp': str(row['timestamp'])
        }
    })


# ----- API 5: Xóa Ảnh -----
@app.route('/api/images/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)
    lenh_db.execute('SELECT filename FROM images WHERE id = %s', (image_id,))
    row = lenh_db.fetchone()

    if not row:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Image not found'}), 404

    # Xóa file vật lý
    filepath = os.path.join(UPLOAD_FOLDER, row['filename'])
    if os.path.exists(filepath):
        os.remove(filepath)

    # Xóa khỏi database
    lenh_db.execute('DELETE FROM images WHERE id = %s', (image_id,))
    conn.commit()
    conn.close()

    # Thông báo Dashboard
    socketio.emit('image_deleted', {'id': image_id})

    return jsonify({'status': 'success', 'message': f'Image {image_id} deleted'})


# ----- API 5b: Xóa Toàn Bộ Ảnh -----
@app.route('/api/images/all', methods=['DELETE'])
def delete_all_images():
    """Xóa toàn bộ ảnh trong hệ thống."""
    try:
        # Xóa tất cả file vật lý trong thư mục uploads
        deleted_count = 0
        for f in os.listdir(UPLOAD_FOLDER):
            fp = os.path.join(UPLOAD_FOLDER, f)
            if os.path.isfile(fp):
                os.remove(fp)
                deleted_count += 1

        # Xóa toàn bộ dữ liệu trong bảng images
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('DELETE FROM images')
        conn.commit()
        conn.close()

        # Thông báo Dashboard
        socketio.emit('all_images_deleted', {'count': deleted_count})
        print(f"[API] 🗑️ Đã xóa toàn bộ {deleted_count} ảnh")

        return jsonify({'status': 'success', 'message': f'Đã xóa {deleted_count} ảnh'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ----- API 6: Trạng Thái Hệ Thống -----
@app.route('/api/status', methods=['GET'])
def get_system_status():
    """Trả thông tin tổng quan về hệ thống."""
    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)

    # Tổng ảnh
    lenh_db.execute('SELECT COUNT(*) as total FROM images')
    total_images = lenh_db.fetchone()['total']

    # Dung lượng ổ đĩa đã dùng
    total_size = 0
    for f in os.listdir(UPLOAD_FOLDER):
        fp = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(fp):
            total_size += os.path.getsize(fp)

    # Danh sách thiết bị
    lenh_db.execute('SELECT * FROM devices')
    devices_rows = lenh_db.fetchall()
    conn.close()

    devices = {}
    for row in devices_rows:
        devices[row['device_id']] = {
            'device_type': row['device_type'],
            'status': device_status_cache.get(row['device_id'], {}).get('status', row['status']),
            'ip_address': row['ip_address'],
            'last_seen': str(row['last_seen']) if row['last_seen'] else '',
            'wifi_rssi': row['wifi_rssi'],
            'total_uploads': row['total_uploads']
        }

    uptime = int(time.time() - SERVER_START_TIME)
    bandwidth = get_current_bandwidth_kbps()

    return jsonify({
        'status': 'success',
        'data': {
            'server': {
                'uptime_seconds': uptime,
                'version': '2.0.0',
                'storage_used_mb': round(total_size / (1024 * 1024), 2),
                'total_images': total_images,
                'bandwidth_kbps': bandwidth,
                'db_type': 'MySQL Server (' + MYSQL_CONFIG['host'] + ')'
            },
            'devices': devices
        }
    })


# ----- Phục vụ file ảnh tĩnh -----
@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ----- Giao diện Web Dashboard -----
@app.route('/')
def index():
    conn = get_db()
    lenh_db = conn.cursor(dictionary=True)
    lenh_db.execute('SELECT * FROM images ORDER BY timestamp DESC')
    images = lenh_db.fetchall()
    conn.close()
    # Convert datetime objects sang string cho Jinja2
    for img in images:
        if img.get('timestamp'):
            img['timestamp'] = str(img['timestamp'])
    return render_template('index.html', images=images)


# ========================= SIMULATOR MANAGEMENT =========================

def cleanup_sim_processes():
    """Tat tat ca simulator khi server tat."""
    for name, proc in sim_processes.items():
        if proc and proc.poll() is None:
            proc.terminate()
            print(f"[SIM] Da tat {name}")

atexit.register(cleanup_sim_processes)


@app.route('/api/sim/start', methods=['POST'])
def start_simulator():
    """Khoi dong simulator process."""
    data = request.get_json() or {}
    sim_type = data.get('type', '')  # 'camera' hoac 'display'

    if sim_type not in SIM_SCRIPTS:
        return jsonify({'status': 'error', 'message': f'Loai sim khong hop le: {sim_type}'}), 400

    script = SIM_SCRIPTS[sim_type]
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)

    # Kiem tra da chay chua
    if sim_type in sim_processes and sim_processes[sim_type] is not None:
        if sim_processes[sim_type].poll() is None:  # Van dang chay
            return jsonify({'status': 'error', 'message': f'{sim_type} simulator da dang chay'}), 409

    # Khoi dong process moi
    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        sim_processes[sim_type] = proc
        print(f"[SIM] ✅ Da khoi dong {sim_type} simulator (PID: {proc.pid})")
        return jsonify({'status': 'success', 'message': f'{sim_type} simulator da khoi dong', 'pid': proc.pid})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sim/stop', methods=['POST'])
def stop_simulator():
    """Tat simulator process."""
    data = request.get_json() or {}
    sim_type = data.get('type', '')

    if sim_type not in SIM_SCRIPTS:
        return jsonify({'status': 'error', 'message': f'Loai sim khong hop le: {sim_type}'}), 400

    if sim_type not in sim_processes or sim_processes[sim_type] is None:
        return jsonify({'status': 'error', 'message': f'{sim_type} simulator chua chay'}), 404

    proc = sim_processes[sim_type]
    if proc.poll() is not None:  # Da tat roi
        sim_processes[sim_type] = None
        return jsonify({'status': 'error', 'message': f'{sim_type} simulator da tat'}), 404

    try:
        proc.terminate()
        proc.wait(timeout=5)
        sim_processes[sim_type] = None
        print(f"[SIM] ⏹️ Da tat {sim_type} simulator")
        return jsonify({'status': 'success', 'message': f'{sim_type} simulator da tat'})
    except Exception as e:
        proc.kill()
        sim_processes[sim_type] = None
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/sim/status', methods=['GET'])
def get_sim_status():
    """Tra ve trang thai cac simulator."""
    statuses = {}
    for sim_type in SIM_SCRIPTS:
        proc = sim_processes.get(sim_type)
        if proc and proc.poll() is None:
            statuses[sim_type] = {'running': True, 'pid': proc.pid}
        else:
            statuses[sim_type] = {'running': False, 'pid': None}
    return jsonify({'status': 'success', 'data': statuses})


# ========================= WEBSOCKET EVENTS =========================

@socketio.on('connect')
def handle_ws_connect(auth=None):
    """Khi browser mới kết nối WebSocket → gửi trạng thái hiện tại."""
    print(f"[WS] 🟢 Browser đã kết nối!")
    # Gửi trạng thái tất cả thiết bị hiện tại
    emit('system_status', {
        'devices': device_status_cache,
        'server_uptime': int(time.time() - SERVER_START_TIME)
    })


@socketio.on('disconnect')
def handle_ws_disconnect():
    print(f"[WS] 🔴 Browser đã ngắt kết nối.")
    # Tự động gửi STREAM_OFF khi browser đóng để camera ngừng chụp liên tục
    try:
        stop_payload = json.dumps({
            'cmd_id': f"auto_stop_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'command': 'STREAM_OFF',
            'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'params': {}
        })
        mqtt_client.publish('iot/camera/cmd', stop_payload, qos=1)
        print(f"[WS] ⏹️ Đã tự động gửi STREAM_OFF do browser ngắt kết nối")
    except Exception as e:
        print(f"[WS] ⚠️ Lỗi gửi STREAM_OFF tự động: {e}")


@socketio.on('send_command')
def handle_send_command(data):
    """
    Browser gửi lệnh điều khiển → Server tạo cmd_id → publish MQTT → Camera nhận.
    data = { "target": "camera", "command": "CAPTURE", "params": {} }
    """
    target = data.get('target', 'camera')
    command = data.get('command', '')
    params = data.get('params', {})

    # Tạo cmd_id duy nhất
    cmd_id = f"cmd_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:4]}"

    # Lưu lệnh vào database
    target_device = f"CAM_NODE_01" if target == 'camera' else f"DISP_NODE_01"
    try:
        conn = get_db()
        lenh_db = conn.cursor(dictionary=True)
        lenh_db.execute('''
            INSERT INTO commands (cmd_id, target_device, command, params, status)
            VALUES (%s, %s, %s, %s, 'PENDING')
        ''', (cmd_id, target_device, command, json.dumps(params)))
        conn.commit()
        conn.close()
    except Exception as e:
        emit('command_result', {'cmd_id': cmd_id, 'status': 'ERROR', 'message': str(e)})
        return

    # Publish lệnh lên MQTT
    mqtt_topic = f"iot/{target}/cmd"
    mqtt_payload = json.dumps({
        'cmd_id': cmd_id,
        'command': command,
        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'params': params
    })

    try:
        mqtt_client.publish(mqtt_topic, mqtt_payload, qos=1)
        print(f"[MQTT] 📤 Đã gửi lệnh {command} (ID: {cmd_id}) lên {mqtt_topic}")
    except Exception as e:
        print(f"[MQTT] ⚠️ Lỗi gửi lệnh: {e}")

    # Phản hồi ngay cho browser biết lệnh đã được gửi đi
    emit('command_sent', {
        'cmd_id': cmd_id,
        'command': command,
        'target': target,
        'status': 'PENDING'
    })


@socketio.on('request_status')
def handle_request_status():
    """Browser yêu cầu cập nhật trạng thái hệ thống."""
    emit('system_status', {
        'devices': device_status_cache,
        'server_uptime': int(time.time() - SERVER_START_TIME)
    })


# ========================= KHỞI ĐỘNG SERVER =========================

if __name__ == '__main__':
    print("=" * 60)
    print("  🚀 IoT Camera System — Web Server v2.0")
    print("  📡 Giao thức: HTTP REST + MQTT + WebSocket")
    print("=" * 60)

    # Buoc 1: Khoi tao Database
    init_db()

    # Buoc 1.5: Load trang thai thiet bi tu DB vao cache
    load_devices_from_db()

    # Bước 2: Kết nối MQTT Broker
    setup_mqtt()

    # Bước 3: Khởi động Heartbeat Monitor (background thread)
    socketio.start_background_task(heartbeat_monitor)
    print(f"[HEARTBEAT] Monitor đã chạy (timeout: {HEARTBEAT_TIMEOUT}s)")

    # Bước 4: Khởi động Flask + SocketIO Server
    print(f"\n[SERVER] 🌐 Dashboard: http://127.0.0.1:5000")
    print(f"[SERVER] 📡 MQTT Broker: {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
    print(f"[SERVER] Đang chờ kết nối từ Camera Node và Display Node...\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
