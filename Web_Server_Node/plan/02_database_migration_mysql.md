# Thiết lập và Chuyển đổi dữ liệu sang Máy chủ Cơ Sở Dữ Liệu MySQL Server

## 1. Tóm tắt quá trình nâng cấp "Enterprise"
Hệ thống quản lý Camera IoT ban đầu đang dùng `SQLite`, đây là cơ sở dữ liệu lưu dưới dạng tệp tin cục bộ phù hợp cho mức độ test Prototype (bản nháp). Quá trình này mô tả quá trình cấu trúc thiết lập kết nối, chuyển giao Query và xây dựng kiến trúc Data với DBMS cấp độ Máy chủ doanh nghiệp: **MySQL Server 2012**. Hệ thống kết nối theo mô hình Remote Database (Máy trạm truy cập Máy chủ DB) qua IP IPv4 Mạng LAN: `192.168.1.121`.

---

## 2. Triển khai Hệ thống Bảng CSDL (Database Schema SQL)

Trên máy chủ lưu trữ MySQL Server (IP: `192.168.1.121`), mở Workbench/SSMS để Generate toàn bộ kiến trúc gồm 4 Table: Image (Hình ảnh Camera), Commands (Trạng thái lệnh), Devices (Thông số sức khỏe kết nối IoT Node), Event_Logs (Hệ thống Log cảm biến cảnh báo).

**Câu lệnh tạo cấu trúc Table Database MySQL thực thi:**
```sql
CREATE DATABASE iot_camera_db;
USE iot_camera_db;

-- Bảng 1: Ảnh chụp
CREATE TABLE images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    file_size INT NOT NULL,
    device_id VARCHAR(50) DEFAULT 'UNKNOWN',
    resolution VARCHAR(20) DEFAULT '160x120',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng 2: Kho lệnh đồng bộ cho Broker
CREATE TABLE commands (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cmd_id VARCHAR(100) NOT NULL UNIQUE,
    target_device VARCHAR(50) NOT NULL,
    command VARCHAR(50) NOT NULL,
    params VARCHAR(500) DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ack_at DATETIME NULL,
    ack_message VARCHAR(500) NULL
);

-- Bảng 3: Cache Memory Status thiết bị (Heartbeat/RSSI/Heap Memory) 
CREATE TABLE devices (
    device_id VARCHAR(50) PRIMARY KEY,
    device_type VARCHAR(30) NOT NULL,
    ip_address VARCHAR(45) NULL,
    status VARCHAR(20) DEFAULT 'offline',
    last_seen DATETIME NULL,
    wifi_rssi INT NULL,
    free_heap INT NULL,
    total_uploads INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Bảng 4: Audit Error Device Logs
CREATE TABLE event_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    level VARCHAR(10) DEFAULT 'INFO',
    event VARCHAR(100) NOT NULL,
    message VARCHAR(500) NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Cấu hình vượt Tường Lửa - Cấp quyền Máy chủ từ xa

Mặc định, cơ sở dữ liệu MySQL luôn đóng khóa chặn hoàn toàn quyền truy vấn lệnh nếu yêu cầu đổ vào từ 1 liên kết IP Máy khách lạ để đề phòng mã độc.
Để máy chạy ứng dụng Web (Flask) có thể Query Insert được dữ liệu từ xa, tại máy thiết lập MySQL (`192.168.1.121`), phải cấu hình **User Privilege** bằng SQL Command:

```sql
-- Tạo tài khoản Database truy cập ở phạm vi Any Host (%) thay vì Localhost
CREATE USER IF NOT EXISTS 'minhmoon2k5'@'%' IDENTIFIED BY 'minhmoon2k5';

-- Ủy quyền cho phép mọi Device Account thao tác dữ liệu toàn phần (Read/Write) vào iot_camera_db
GRANT ALL PRIVILEGES ON iot_camera_db.* TO 'minhmoon2k5'@'%';

-- Bắt Server Refresh Load lại Table Policies Privilege
FLUSH PRIVILEGES;
```

---

## 4. Chuyển đổi Mã lập trình Python (SQLite -> MySQL)

Tại Server Backend xử lý API (`app.py` và `system_analytics.py`), thực hiện Refactoring đổi Library Cấu hình CSDL.
Sử dụng thư viện `mysql.connector`. Chạy lệnh chuẩn bị thư viện:
```powershell
pip install mysql-connector-python
```

### 4.1. Thiết lập Cấu hình Dictionary CSDL trong Code
Thay đổi phương thức Connection để kết nối theo dạng TCP/IP Protocol:
```python
import mysql.connector

MYSQL_CONFIG = {
    'host': '192.168.1.121',  # Trỏ về Máy trạm PC Desktop
    'port': 3306,             # Cổng mặc định MySQL Server Listen tcp
    'user': 'minhmoon2k5',    # Thông tin tài khoản Authorization
    'password': 'minhmoon2k5',
    'database': 'iot_camera_db',
    'autocommit': False,      # Quản lý dòng Transaction chặn Deadlock
}

def get_db():
    return mysql.connector.connect(**MYSQL_CONFIG)
```

### 4.2. Khắc phục bất đồng bộ Syntax Ngôn ngữ SQL
Thực hiện cấu hình sửa mã toàn mã nguồn đáp ứng 3 điểm khác biệt của System MySQL:
1. **Placeholder Parameters (Tham số chống SQL Injection):** Mọi tham chiếu lệnh bảo mật SQLite đang dùng Syntax `?` phải đổi cấu trúc đồng loạt toàn dự án sang MySQL Format `%s`.
2. **Key Update Upsert (Xung đột khóa):** Hàm `ON CONFLICT` từ SQLite khi nhận Heartbeat của Thiết bị phải thay đổi thuật toán, chuyển đổi sang toán tử cấp cao dùng riêng cho Engine InnoDB MySQL là `ON DUPLICATE KEY UPDATE` giúp tối ưu xử lí tốc độ lưu lượng cao.
3. **Cursor Dictionary Access Column (Mapping Khóa mảng):** Việc lấy dữ liệu của MySQL phải chèn Arguments `dictionary=True` vào lệnh tạo Interface `conn.cursor(dictionary=True)` thay vì dùng Object `conn.row_factory` cũ, cho phép bóc tách cấu trúc Data JSON thành dạng mảng ánh xạ `<Cột>:<Giá trị>` thay vì trả mảng Tuple index vô nghĩa.

**Ví dụ một đoạn code mẫu cấu trúc Query Upsert Heartbeat thiết bị đã refactor cho MySQL Protocol:**
```python
lenh_db = conn.cursor(dictionary=True)
lenh_db.execute('''
    INSERT INTO devices (device_id, device_type, ip_address, status, last_seen, wifi_rssi, free_heap)
    VALUES (%s, %s, %s, 'online', %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        ip_address = VALUES(ip_address),
        status = 'online',
        last_seen = VALUES(last_seen),
        wifi_rssi = VALUES(wifi_rssi),
        free_heap = VALUES(free_heap)
''', (device_id, device_type, ip_address, now, wifi_rssi, free_heap))
```
