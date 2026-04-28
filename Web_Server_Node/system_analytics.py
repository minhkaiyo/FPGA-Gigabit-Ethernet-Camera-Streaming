"""
=============================================================================
 IoT Camera System - Professional Data Analytics Tool
 Phien ban: 2.0 (MySQL Server Edition)
=============================================================================
"""
import mysql.connector
import os
import sys
from datetime import datetime

# Fix Unicode encoding tren Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Cau hinh ket noi MySQL (giong voi app.py)
MYSQL_CONFIG = {
    'host': '192.168.1.121',
    'port': 3306,
    'user': 'minhmoon2k5',
    'password': 'minhmoon2k5',
    'database': 'iot_camera_db',
}

def get_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def show_general_stats():
    conn = get_connection()
    lenh_db = conn.cursor(dictionary=True)
    
    # 1. Tổng số lượng
    lenh_db.execute("SELECT COUNT(*) as total FROM images")
    total_images = lenh_db.fetchone()['total']
    
    lenh_db.execute("SELECT COUNT(*) as total FROM devices")
    total_devices = lenh_db.fetchone()['total']
    
    # 2. Thiết bị online
    lenh_db.execute("SELECT COUNT(*) as total FROM devices WHERE status='online'")
    online_devices = lenh_db.fetchone()['total']

    # 3. Tính dung lượng ảnh (từ file thực tế)
    upload_dir = 'uploads'
    total_size = 0
    if os.path.exists(upload_dir):
        for f in os.listdir(upload_dir):
            total_size += os.path.getsize(os.path.join(upload_dir, f))
    
    print_header("THỐNG KÊ TỔNG QUAN HỆ THỐNG")
    print(f" 📡 Tổng số thiết bị đăng ký: {total_devices}")
    print(f" 🟢 Thiết bị hiện đang Online: {online_devices}")
    print(f" 📸 Tổng số ảnh đã chụp:      {total_images}")
    print(f" 💾 Tổng dung lượng lưu trữ:  {total_size / (1024*1024):.2f} MB")
    print(f" 🗃️  Database Engine:          MySQL Server")
    
    conn.close()

def show_device_health():
    print_header("BÁO CÁO CHI TIẾT THIẾT BỊ")
    conn = get_connection()
    lenh_db = conn.cursor(dictionary=True)
    
    lenh_db.execute("""
        SELECT device_id, status, wifi_rssi, last_seen 
        FROM devices
    """)
    rows = lenh_db.fetchall()
    
    if not rows:
        print(" Chua co thiet bi nao duoc dang ky.")
        conn.close()
        return

    print(f"{'Device ID':<15} | {'Status':<10} | {'WiFi (dBm)':<11} | {'Lan cuoi thay'}")
    print("-" * 60)
    for row in rows:
        status_icon = "✅" if row['status'] == 'online' else "❌"
        rssi = row['wifi_rssi'] if row['wifi_rssi'] else "N/A"
        last_seen = str(row['last_seen']) if row['last_seen'] else "Chua biet"
        print(f"{row['device_id']:<15} | {status_icon} {row['status']:<7} | {str(rssi):<11} | {last_seen}")
    
    conn.close()

def show_recent_errors():
    print_header("CẢNH BÁO LỖI HỆ THỐNG GẦN ĐÂY")
    conn = get_connection()
    lenh_db = conn.cursor(dictionary=True)
    
    lenh_db.execute("""
        SELECT timestamp, device_id, message 
        FROM event_logs 
        WHERE level='ERROR' 
        ORDER BY timestamp DESC LIMIT 5
    """)
    rows = lenh_db.fetchall()
    
    if not rows:
        print(" 🎉 Tuyệt vời! Không phát hiện lỗi nghiêm trọng nào.")
    else:
        for row in rows:
            print(f" [{row['timestamp']}] ⚠️ {row['device_id']}: {row['message']}")
    
    conn.close()

if __name__ == "__main__":
    print("="*60)
    print("  IoT Camera System - Data Analytics Tool v2.0")
    print("  Database: MySQL Server @ 127.0.0.1:3306")
    print("="*60)

    try:
        # Test ket noi truoc
        test_conn = get_connection()
        test_conn.close()
        
        show_general_stats()
        show_device_health()
        show_recent_errors()
        print("\n" + "="*60)
        print("  Bao cao duoc trich xuat tu dong boi IoT System Analytics")
        print("="*60 + "\n")
    except mysql.connector.Error as e:
        print(f"\n❌ Khong the ket noi MySQL: {e}")
        print("Hay dam bao MySQL Server dang chay va database 'iot_camera_db' da duoc tao!")
