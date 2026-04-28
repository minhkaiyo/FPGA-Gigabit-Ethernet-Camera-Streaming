#include <WiFi.h>
#include <WebServer.h>
#include <SPIFFS.h>
#include <TFT_eSPI.h>
#include <TJpg_Decoder.h>

const char* AP_SSID = "NavDisplay";
const char* AP_PASS = "12345678";

// Buffer lưu ảnh JPEG (Cấp phát 30KB - thừa đủ cho ảnh 160x128)
#define JPEG_BUF_SIZE 30000
uint8_t* jpgBuf = nullptr;
size_t   jpgLen = 0;

float gpsSpeed = 0;
bool mapReceived = false;

TFT_eSPI tft = TFT_eSPI();
WebServer server(80);

// Hàm Callback được TJpg_Decoder gọi để vẽ từng "khối pixel" lên màn hình
bool onJpgBlock(int16_t x, int16_t y, uint16_t w, uint16_t h, uint16_t* bitmap) {
    if (y >= tft.height() || x >= tft.width()) return false;
    tft.pushImage(x, y, w, h, bitmap); // Đẩy rất nhanh qua SPI
    return true;
}

// Xử lý luồng file JPEG được Upload từ Điện thoại
void handleMapUpload() {
    HTTPUpload& upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
        jpgLen = 0;
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (jpgLen + upload.currentSize <= JPEG_BUF_SIZE) {
            memcpy(jpgBuf + jpgLen, upload.buf, upload.currentSize);
            jpgLen += upload.currentSize;
        }
    } else if (upload.status == UPLOAD_FILE_END) {
        mapReceived = true;
    }
}

// Xác nhận việc Upload thành công
void handleMapDone() {
    if (server.hasArg("speed")) gpsSpeed = server.arg("speed").toFloat();
    server.send(200, "text/plain", "OK"); // Phản hồi thật nhanh về điện thoại
}

// Cung cấp file HTML (Web App) chứa bản đồ cho điện thoại
void handleRoot() {
    File f = SPIFFS.open("/index.html", "r");
    if (!f) {
        server.send(500, "text/plain", "Error: /index.html not found in SPIFFS");
        return;
    }
    server.streamFile(f, "text/html");
    f.close();
}

void setup() {
    Serial.begin(115200);

    // Cấp phát vùng nhớ cho JPEG
    jpgBuf = (uint8_t*)malloc(JPEG_BUF_SIZE);
    
    // Khởi tạo Màn hình ST7735
    tft.init();
    tft.setRotation(1); // Xoay ngang (160x128)
    tft.fillScreen(TFT_BLACK);
    
    // Khởi tạo Bộ Nhớ
    if (!SPIFFS.begin(true)) {
        Serial.println("SPIFFS mount failed!");
    }

    // Phát WiFi (Không cần Internet)
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
    
    // Thiết lập Web Server
    server.on("/", HTTP_GET, handleRoot);
    server.on("/update", HTTP_POST, handleMapDone, handleMapUpload);
    server.begin();

    // Cấu hình mạch giải mã JPEG
    TJpgDec.setJpgScale(1); 
    TJpgDec.setCallback(onJpgBlock);

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString("Ket Noi WiFi:", 10, 30, 2);
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.drawString(AP_SSID, 10, 50, 2);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.drawString("Vao 192.168.4.1", 10, 80, 2);
}

void loop() {
    server.handleClient(); // Xử lý liên tục

    if (mapReceived) {
        mapReceived = false;
        
        // Render Ảnh ra màn hình
        uint16_t w=0, h=0;
        TJpgDec.getJpgSize(&w, &h, jpgBuf, jpgLen);
        TJpgDec.drawJpg(0, 0, jpgBuf, jpgLen);

        // Vẽ thêm Vận tốc đè lên bản đồ
        tft.fillRect(0, tft.height()-12, tft.width(), 12, TFT_BLACK);
        tft.setTextColor(TFT_GREEN, TFT_BLACK);
        tft.setCursor(2, tft.height()-10);
        tft.printf("%.0f km/h", gpsSpeed);
    }
}
