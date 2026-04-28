#Node 2 : Display Node(ESP32 + TFT 1.8 ")

#include <HTTPClient.h>
#include <SPI.h>
#include <TFT_eSPI.h> // Thư viện đồ họa cho màn hình TFT
#include <WiFi.h>


TFT_eSPI tft = TFT_eSPI();

const char *ssid = "TEN_WIFI_CUA_BAN";
const char *password = "MAT_KHAU_WIFI";
const char *latestImageUrl = "http://IP_CUA_MAY_TINH:5000/api/latest";

// Cấu hình Nút nhấn (Dùng pull-up nội)
#define BTN_UP 12
#define BTN_DOWN 14
#define BTN_OK 27
#define BTN_BACK 26

void setup() {
  Serial.begin(115200);

  // Khởi tạo màn hình
  tft.init();
  tft.setRotation(1); // Xoay ngang
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.drawString("Connecting to WiFi...", 10, 10, 2);

  // Khởi tạo Nút nhấn
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  pinMode(BTN_OK, INPUT_PULLUP);
  pinMode(BTN_BACK, INPUT_PULLUP);

  // Kết nối WiFi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  tft.fillScreen(TFT_BLACK);
  tft.drawString("WiFi Connected!", 10, 10, 2);
  delay(1000);

  drawMenu();
}

void loop() {
  // 1. Kiểm tra thao tác nhấn nút
  if (digitalRead(BTN_OK) == LOW) {
    // Gọi lệnh gửi tín hiệu chụp cho Server
    // ...
    delay(200); // Debounce
  }

  // 2. Logic cập nhật ảnh (Có thể chạy bằng millis() thay cho delay)
  // downloadAndDisplayImage();
  // delay(5000);
}

void drawMenu() {
  tft.fillScreen(TFT_BLACK);
  tft.fillRect(0, 0, 160, 20, TFT_BLUE);
  tft.setTextColor(TFT_WHITE, TFT_BLUE);
  tft.drawString(" IoT Camera ", 40, 2, 2);

  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.drawString("Press OK to update", 10, 100, 2);
}

void downloadAndDisplayImage() {
  // Dùng HTTPClient Get ảnh từ server
  // Giải mã JPG (dùng thư viện TJpg_Decoder) hiển thị lên TFT
}
