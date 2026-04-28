# Triển khai Ngrok và Khắc phục lỗi bảo mật Mixed Content

## 1. Vai trò của Ngrok trong dự án
Hệ thống Web Server Python (Flask) được chạy trên máy tính cá nhân tại cổng Localhost `5000` (`http://127.0.0.1:5000`). Bằng cách sử dụng **Ngrok**, máy chủ nội bộ này được ánh xạ (tunnel) tạo ra một Public URL an toàn (HTTPS) để có thể phục vụ giao diện Web Dashboard cho bất kỳ thiết bị nào (điện thoại, máy tính khác) trên mạng Internet mà không cần phải thực hiện cấu hình Mở Cổng Router (Port Forwarding).

## 2. Các bước thiết lập và cấu hình Ngrok

### Bước 2.1. Đăng ký & Chứng thực Authtoken
Mở PowerShell tại máy tính đang chạy Web Server, thiết lập Authtoken kết nối tài khoản Ngrok đến ứng dụng Ngrok Local:
```powershell
ngrok config add-authtoken <YOUR_NGROK_AUTH_TOKEN>
```

### Bước 2.2. Kích hoạt Tunnel cho Web Server
Để ánh xạ cổng `5000` của Flask Server ra Internet, chạy lệnh:
```powershell
ngrok http 5000
```
Sau khi chạy, giao diện dòng lệnh của Ngrok sẽ trả về một đường link có định dạng `https://<random_id>.ngrok-free.app`.

---

## 3. Khắc phục lỗi Mixed Content (Nội dung hỗn hợp)

### Nguyên nhân sự cố
Ngrok cấp phát một đường link bảo mật bằng phương thức mã hóa **HTTPS** (ví dụ: `https://abcd.ngrok.io`). Tuy nhiên, trong mã nguồn ban đầu của Frontend (`index.html`), địa chỉ liên kết lại được lập trình theo kiểu gán cố định kết nối đến Backend:
```javascript
// Cấu hình ban đầu gây lỗi
const SERVER_URL = 'http://127.0.0.1:5000';
```
Do Frontend được truy cập qua đường liên kết bảo mật (`HTTPS`) nhưng lại nỗ lực gửi các gói lệnh API và tải ảnh Camera Node về thông qua đường liên kết không được mã hóa (`HTTP`), nên cơ chế bảo mật trên trình duyệt Web thế hệ mới (Chrome, Safari, Firefox) sẽ can thiệp và kích hoạt chính sách **Block Mixed Content** (Khóa Luồng Nội dung hỗn hợp). Kết cục: Mọi Data nhận từ ESP32 sẽ bị chặn lại ở trình duyệt báo lỗi (Fetch failed / Blocked).

### Cách xử lý: Dynamic URL Domain Routing
Không dùng thiết lập tĩnh gán chết theo IP, mà viết hàm JS sử dụng Window Object (`window.location`) tự động điều phối để Frontend đi theo cùng giao thức và Server lưu trữ mà Web đã được load ban đầu.

**Mã nguồn Code JS khắc phục được cập nhật tại `index.html`:**
```javascript
/* 
Sử dụng chính Protocol khởi tạo (http hoặc https) 
Và Host khởi tạo (127.0.0.1:5000 hoặc xyz.ngrok.app) 
Để trỏ Backend API linh hoạt ở mọi môi trường mạng.
*/
const SERVER_URL = window.location.protocol + '//' + window.location.host;

// Tích hợp cho WebSocket Client
const socket = io(SERVER_URL);

// Ví dụ một hàm Call API sử dụng đường link động, triệt tiêu lỗi Mixed Content:
function updateServerInfo() {
    fetch(SERVER_URL + '/api/status')
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('server-version').textContent = 'v' + data.data.server.version;
            }
        });
}
```

### Kết quả
Sau hướng xử lý này, nền tảng IoT Web Server tự động tương thích với IP Private ở chế độ Development (`http://127.x.x.x`) lẫn Public Domain Tunnel trên Production (`https://*.ngrok-free.app`), và nhận API hình ảnh gửi về của phần cứng liên tục mà không còn xuất hiện cờ báo lỗi Console Security Exception.  
