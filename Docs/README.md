# Tổ chức dự án Đồ án 1 - Hệ thống Giám sát Hình ảnh Từ xa IoT (ESP32 + OV7670)

Dự án này là một hệ thống IoT hoàn chỉnh với thiết kế Edge-Server-Client Node.

## Cấu trúc Thư mục

- `Web_Server_Node/`
  - Khu vực Backend và CSDL.
  - Sử dụng Python (Flask) để tạo REST API và giao diện Web.
  - SQLite được dùng để lưu metadata của ảnh. Toàn bộ hình ảnh thực tế lưu trong thư mục `uploads/`.
- `Camera_Node/`
  - Firmware C++ (Arduino IDE) cho vi điều khiển ESP32 và Camera OV7670.
  - Nút Edge đóng vai trò thiết bị thu thập đầu cuối (Sensor Node).
- `Display_Node/`
  - Firmware C++ (Arduino IDE) cho vi điều khiển ESP32 và màn hình TFT hiển thị.
  - Đóng vai trò làm Client để theo dõi và đưa tín hiệu thao tác lên hệ thống.
- `Docs/` (Thư mục này)
  - Chứa sơ đồ mạch điện (Schematics), lưu đồ thuật toán và tài liệu dùng cho báo cáo.

## Các bước chuẩn bị môi trường:
1. **Web Server:**
   - Cài đặt Python 3.
   - Chạy `pip install -r Web_Server_Node/requirements.txt`
   - Bật server: `python Web_Server_Node/app.py`
2. **Arduino Nodes:**
   - Cài đặt ESP32 trong Boards Manager của Arduino IDE.
   - Upload code thông qua cổng USB tương ứng.
