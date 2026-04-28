// =============================================================
// IoT Camera System — Camera Node v3.1  (Dual-Core FreeRTOS)
// OV7670 (non-FIFO) + ST7735 TFT + WiFi + MQTT + HTTP Stream
// ESP32 DevKit V1
// =============================================================
//
// ARCHITECTURE (Dual-Core):
//   Core 1 (Arduino loop) : Camera capture + TFT display  — REAL-TIME
//   Core 0 (networkTask)  : WiFi, MQTT, Heartbeat, HTTP   — BACKGROUND
//
// Nhu vay TFT se KHONG BAO GIO bi khung/lag do mang!
// =============================================================

// ========================= CHE DO CAMERA =========================

#define MODE QQVGA // 160x120 — Vua voi ST7735 va du nhe de stream
#define COLOR RGB565
#define ROTATION 1 // Man hinh ngang

// ========================= THU VIEN =========================

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <OV7670.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>

// ========================= CAU HINH MANG =========================

const char *WIFI_SSID = "VanMinh";
const char *WIFI_PASS = "11111111";

// ========================= CAU HINH MQTT (Broker Cong Cong)
// =========================
const char *MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char *MQTT_USER = "";
const char *MQTT_PASS = "";
const char *MQTT_CLIENT_ID = "esp32_cam_minh_hust_2026";
const char *DEVICE_ID = "CAM_NODE_01";
const char *FIRMWARE_VERSION = "3.2.0 (Global)";

// ========================= CAU HINH SERVER (Link ngrok)
// =========================
String SERVER_URL = "https://unpranked-presufficiently-amare.ngrok-free.dev";

// ========================= MQTT TOPICS =========================

const char *TOPIC_CMD = "iot/camera/cmd";
const char *TOPIC_ACK = "iot/camera/ack";
const char *TOPIC_STATUS = "iot/camera/status";
const char *TOPIC_HEARTBEAT = "iot/system/heartbeat";
const char *TOPIC_LOG = "iot/system/log";

// ========================= CAU HINH THOI GIAN =========================

const unsigned long HEARTBEAT_INTERVAL = 2000; // 2s heartbeat
const unsigned long STREAM_INTERVAL = 100;     // ~10 FPS stream
const unsigned long WIFI_RECONNECT_DELAY = 3000;
const unsigned long MQTT_RECONNECT_DELAY = 3000;

// ========================= CHAN GPIO =========================

const int LED_STATUS = 2;

// ========================= PIN OV7670 =========================

const camera_config_t cam_conf = {.D0 = 36,
                                  .D1 = 39,
                                  .D2 = 34,
                                  .D3 = 35,
                                  .D4 = 32,
                                  .D5 = 33,
                                  .D6 = 25,
                                  .D7 = 26,
                                  .XCLK = 27,
                                  .PCLK = 14,
                                  .VSYNC = 13,
                                  .xclk_freq_hz = 10000000,
                                  .ledc_timer = LEDC_TIMER_0,
                                  .ledc_channel = LEDC_CHANNEL_0};

// ========================= PIN TFT ST7735 =========================

#define TFT_CS 5
#define TFT_DC 16
#define TFT_RST 17

// ========================= OBJECTS =========================

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
OV7670 cam;

// WiFi + MQTT (chi dung trong networkTask — Core 0)
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

uint16_t *lineBuf;
uint16_t camW = 160, camH = 120;

// ========================= SHARED STATE (thread-safe)
// =========================

// Frame buffer chia se giua 2 core
// Core 1 ghi vao, Core 0 doc ra de gui HTTP
volatile bool frameReady = false;       // Co frame moi san sang?
volatile bool isStreaming = false;      // Lenh STREAM_ON/OFF tu MQTT
volatile bool captureRequested = false; // Lenh CAPTURE tu MQTT
volatile bool mqttConnected = false;

// Double buffer de tranh xung dot
uint8_t *frameBufferA = NULL; // Core 1 dang ghi
uint8_t *frameBufferB = NULL; // Core 0 dang doc/gui
SemaphoreHandle_t frameMutex;

// Thong ke
volatile unsigned long frameCount = 0;
volatile unsigned long streamFPS = 0;

// Lenh capture
String pendingCaptureId = "";

// ========================= SETUP (Core 1) =========================

void setup() {
  setCpuFrequencyMhz(240);
  Serial.begin(115200);
  pinMode(LED_STATUS, OUTPUT);
  digitalWrite(LED_STATUS, LOW);

  Serial.println(
      "\n============================================================");
  Serial.println("  IoT Camera System — Camera Node v3.1 (Dual-Core)");
  Serial.println("  Core 1: Camera + TFT  |  Core 0: WiFi + MQTT + HTTP");
  Serial.println(
      "============================================================");

  // --- Frame buffers ---
  const uint32_t FRAME_SIZE = camW * camH * 2; // 38400 bytes
  frameBufferA = (uint8_t *)malloc(FRAME_SIZE);
  frameBufferB = (uint8_t *)malloc(FRAME_SIZE);
  frameMutex = xSemaphoreCreateMutex();

  if (!frameBufferA || !frameBufferB) {
    Serial.println("[ERROR] Khong du RAM cho frame buffer!");
  } else {
    Serial.printf("[MEM] Double buffer: 2 x %d = %d bytes\n", FRAME_SIZE,
                  FRAME_SIZE * 2);
    Serial.printf("[MEM] Free heap: %d bytes\n", ESP.getFreeHeap());
  }

  // --- Init I2C ---
  Wire.begin();
  Wire.setClock(400000);

  // --- Init TFT ST7735 ---
  tft.initR(INITR_BLACKTAB);
  tft.setRotation(ROTATION);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setCursor(4, 10);
  tft.println("IoT Camera v3.1");
  tft.setCursor(4, 25);
  tft.println("Dual-Core Mode");
  Serial.println("[TFT] ST7735 initialized OK");

  // --- Init Camera OV7670 ---
  esp_err_t err = cam.init(&cam_conf, MODE, COLOR);
  if (err != ESP_OK) {
    Serial.println("[CAM] init ERROR!");
    tft.setCursor(4, 45);
    tft.setTextColor(ST77XX_RED);
    tft.println("CAM INIT FAIL!");
    while (1)
      delay(1000);
  }

  cam.setPCLK(2, DBLV_CLK_x4);
  cam.vflip(false);

  Serial.printf("[CAM] MID = %X  PID = %X\n", cam.getMID(), cam.getPID());
  Serial.printf("[CAM] Resolution: %d x %d\n", camW, camH);

  tft.setCursor(4, 45);
  tft.setTextColor(ST77XX_GREEN);
  tft.printf("CAM OK: %dx%d", camW, camH);

  tft.setCursor(4, 60);
  tft.setTextColor(ST77XX_CYAN);
  tft.println("Starting network...");

  // --- Khoi dong Network Task tren Core 0 ---
  xTaskCreatePinnedToCore(networkTask,   // Ham task
                          "NetworkTask", // Ten
                          16384, // Tang stack size tu 8192 len 16384 cho HTTPS
                          NULL,  // Tham so
                          1,     // Priority (1 = binh thuong)
                          NULL,  // Task handle
                          0      // Core 0
  );

  Serial.println("[SETUP] Network task da chay tren Core 0");

  // Doi WiFi ket noi (toi da 5s) de hien thi IP len TFT
  unsigned long waitStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - waitStart < 5000) {
    delay(100);
  }

  if (WiFi.status() == WL_CONNECTED) {
    tft.setCursor(4, 75);
    tft.setTextColor(ST77XX_GREEN);
    tft.printf("IP: %s", WiFi.localIP().toString().c_str());
  }

  delay(1000);
  tft.fillScreen(ST77XX_BLACK);
  Serial.println("[SETUP] Bat dau hien thi video len TFT...\n");
}

// ========================= MAIN LOOP — Core 1 (Camera + TFT)
// ========================= Chi lam 1 viec: chup + hien thi. KHONG co bat ky
// code mang nao o day!

void loop() {
  // Chup tung dong va hien thi len TFT
  for (uint16_t y = 0; y < camH; y++) {
    lineBuf = cam.getLine(y + 1);
    tft.drawRGBBitmap(0, y, lineBuf, camW, 1);

    // Copy vao buffer A (cho stream/capture) — chi khi can
    if (frameBufferA && (isStreaming || captureRequested)) {
      memcpy(frameBufferA + (y * camW * 2), (uint8_t *)lineBuf, camW * 2);
    }
  }

  // Khi chup xong 1 frame day du, swap buffer cho Core 0
  if (isStreaming || captureRequested) {
    if (xSemaphoreTake(frameMutex, 0) == pdTRUE) {
      // Swap A <-> B
      uint8_t *tmp = frameBufferB;
      frameBufferB = frameBufferA;
      frameBufferA = tmp;
      frameReady = true;
      xSemaphoreGive(frameMutex);
    }
  }

  // LED sang khi WiFi + MQTT OK
  digitalWrite(LED_STATUS, mqttConnected ? HIGH : ((millis() / 500) % 2));
}

// ========================= NETWORK TASK — Core 0 =========================
// Xu ly toan bo: WiFi, MQTT, Heartbeat, HTTP stream
// Chay doc lap, KHONG anh huong den TFT

void networkTask(void *pvParameters) {
  Serial.println("[NET-Core0] Network task started!");

  // --- Ket noi WiFi ---
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("[WiFi] Dang ket noi '%s'...\n", WIFI_SSID);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 40) {
    vTaskDelay(250 / portTICK_PERIOD_MS);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] OK! IP: %s  RSSI: %d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    Serial.println("\n[WiFi] THAT BAI! Se thu lai...");
  }

  // --- Cau hinh MQTT ---
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(onMQTTMessage);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(30);    // Keepalive 30s
  mqttClient.setSocketTimeout(5); // Socket timeout 5s

  // --- Bien cuc bo cho task ---
  unsigned long lastHB = 0;
  unsigned long lastStream = 0;
  unsigned long lastWiFiChk = 0;
  unsigned long lastMQTTChk = 0;
  unsigned long fpsCounter = 0;
  unsigned long lastFPSCalc = 0;

  // ===== VONG LAP CHINH CUA CORE 0 =====
  while (true) {
    unsigned long now = millis();

    // --- 1. Duy tri WiFi ---
    if (WiFi.status() != WL_CONNECTED) {
      if (now - lastWiFiChk > WIFI_RECONNECT_DELAY) {
        lastWiFiChk = now;
        Serial.println("[WiFi] Mat ket noi! Reconnecting...");
        WiFi.reconnect();
      }
      vTaskDelay(100 / portTICK_PERIOD_MS);
      continue;
    }

    // --- 2. Duy tri MQTT ---
    if (!mqttClient.connected()) {
      mqttConnected = false;
      if (now - lastMQTTChk > MQTT_RECONNECT_DELAY) {
        lastMQTTChk = now;
        connectMQTT();
      }
    } else {
      mqttConnected = true;
    }
    mqttClient.loop(); // Non-blocking khi da ket noi

    // --- 3. Gui Heartbeat ---
    if (now - lastHB >= HEARTBEAT_INTERVAL) {
      lastHB = now;
      if (mqttConnected)
        sendHeartbeat();
    }

    // --- 4. Gui frame HTTP (khi dang stream) ---
    if (isStreaming && frameReady) {
      if (now - lastStream >= STREAM_INTERVAL) {
        lastStream = now;
        sendFrameToServer();
        fpsCounter++;
        frameReady = false;
      }
    }

    // --- 5. Xu ly lenh CAPTURE ---
    if (captureRequested && frameReady) {
      captureAndUpload(pendingCaptureId);
      captureRequested = false;
      frameReady = false;
    }

    // --- 6. Tinh FPS ---
    if (now - lastFPSCalc >= 1000) {
      streamFPS = fpsCounter;
      fpsCounter = 0;
      lastFPSCalc = now;
    }

    // Nhuong CPU cho task khac (1ms)
    vTaskDelay(1 / portTICK_PERIOD_MS);
  }
}

// ========================= MQTT =========================

void connectMQTT() {
  Serial.printf("[MQTT] Ket noi %s:%d (user: %s)...\n", MQTT_BROKER, MQTT_PORT,
                MQTT_USER);

  // QUAN TRONG: Dong socket cu truoc khi thu ket noi lai
  // Neu khong, PubSubClient se bi "ket" o socket cu da chet
  wifiClient.stop();
  vTaskDelay(200 / portTICK_PERIOD_MS); // Cho TCP stack don dep

  // Kiem tra xem co the ket noi TCP den Broker khong
  Serial.println("[MQTT] Test TCP connection...");
  WiFiClient testClient;
  if (!testClient.connect(MQTT_BROKER, MQTT_PORT, 3000)) {
    Serial.println("[MQTT] ✗ Khong the ket noi TCP! Kiem tra:");
    Serial.println("  1. Mosquitto dang chay?");
    Serial.println("  2. Firewall cho phep port 1883?");
    Serial.printf("  3. ESP32 IP: %s\n", WiFi.localIP().toString().c_str());
    testClient.stop();
    mqttConnected = false;
    return;
  }
  testClient.stop();
  Serial.println("[MQTT] TCP OK! Dang gui MQTT CONNECT...");
  vTaskDelay(100 / portTICK_PERIOD_MS);

  // LWT payload
  StaticJsonDocument<200> lwt;
  lwt["device_id"] = DEVICE_ID;
  lwt["device_type"] = "camera";
  lwt["status"] = "offline";
  lwt["message"] = "Camera Node mat ket noi";
  String lwtStr;
  serializeJson(lwt, lwtStr);

  if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS, TOPIC_HEARTBEAT,
                         1, false, lwtStr.c_str())) {
    Serial.println("[MQTT] ✓ Ket noi thanh cong!");
    mqttConnected = true;
    mqttClient.subscribe(TOPIC_CMD, 1);
    Serial.printf("[MQTT] Subscribed: %s\n", TOPIC_CMD);
    sendLog("INFO", "MQTT_CONNECTED", "Da ket noi MQTT Broker");
  } else {
    int state = mqttClient.state();
    Serial.printf("[MQTT] ✗ THAT BAI! state=%d\n", state);
    if (state == 5)
      Serial.println("  -> SAI USERNAME/PASSWORD!");
    else if (state == 4)
      Serial.println("  -> KHONG CO QUYEN!");
    else if (state == -4)
      Serial.println("  -> TIMEOUT — Broker qua cham");
    else if (state == -2)
      Serial.println("  -> TCP CONNECT FAIL — Socket loi");
    mqttConnected = false;
  }
}

// ========================= MQTT CALLBACK =========================

void onMQTTMessage(char *topic, byte *payload, unsigned int length) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.printf("[MQTT] JSON error: %s\n", err.c_str());
    return;
  }

  String command = doc["command"] | "";
  String cmdId = doc["cmd_id"] | "";

  Serial.printf("[CMD] Lenh: %s (ID: %s)\n", command.c_str(), cmdId.c_str());

  if (command == "CAPTURE") {
    pendingCaptureId = cmdId;
    captureRequested = true;
    sendACK(cmdId, "OK", "Dang chup...");

  } else if (command == "STREAM_ON") {
    isStreaming = true;
    Serial.println("[STREAM] ON");
    sendACK(cmdId, "OK", "Stream ON");

  } else if (command == "STREAM_OFF") {
    isStreaming = false;
    Serial.println("[STREAM] OFF");
    sendACK(cmdId, "OK", "Stream OFF");

  } else if (command == "RESTART") {
    sendACK(cmdId, "OK", "Restarting...");
    vTaskDelay(500 / portTICK_PERIOD_MS);
    ESP.restart();

  } else {
    sendACK(cmdId, "ERROR", "Lenh khong hop le: " + command);
  }
}

// ========================= GUI FRAME LEN SERVER (Core 0)
// =========================

// Global objects de tai su dung, tranh phan manh RAM
WiFiClientSecure globalSecureClient;
HTTPClient globalHttp;
bool streamConnected = false;

void sendFrameToServer() {
  if (!frameBufferB || WiFi.status() != WL_CONNECTED) {
    if (streamConnected) {
      globalHttp.end();
      streamConnected = false;
    }
    return;
  }

  String url = SERVER_URL + "/api/stream_frame";

  if (!streamConnected) {
    globalSecureClient.setInsecure();
    globalHttp.begin(globalSecureClient, url);
    globalHttp.addHeader("Connection", "keep-alive");
    streamConnected = true;
  }

  globalHttp.addHeader("Content-Type", "application/octet-stream");
  globalHttp.addHeader("X-Device-ID", DEVICE_ID);
  globalHttp.addHeader("X-Frame-Width", "160");
  globalHttp.addHeader("X-Frame-Height", "120");
  globalHttp.addHeader("X-Frame-Format", "RGB565");
  globalHttp.setTimeout(3000);

  uint8_t *sendBuf = NULL;
  if (xSemaphoreTake(frameMutex, 50 / portTICK_PERIOD_MS) == pdTRUE) {
    sendBuf = frameBufferB;
    xSemaphoreGive(frameMutex);
  }

  if (sendBuf) {
    int code = globalHttp.POST(sendBuf, 160 * 120 * 2);
    if (code != 200 && code != 201) {
      Serial.printf("[STREAM] HTTP err: %d\n", code);
      globalHttp.end();
      streamConnected = false;
    }
  }
}

// ========================= CAPTURE + UPLOAD (Core 0) =========================

void captureAndUpload(String cmdId) {
  Serial.println("[CAPTURE] Bat dau upload anh chat luong cao...");

  // 1. Dong ket noi stream va doi 200ms de dọn dẹp RAM SSL
  if (isStreaming || streamConnected) {
    globalHttp.end();
    streamConnected = false;
    vTaskDelay(200 / portTICK_PERIOD_MS);
  }

  uint8_t *sendBuf = NULL;
  if (xSemaphoreTake(frameMutex, 200 / portTICK_PERIOD_MS) == pdTRUE) {
    sendBuf = frameBufferB;
    xSemaphoreGive(frameMutex);
  }

  if (!sendBuf) {
    sendACK(cmdId, "ERROR", "Buffer Busy");
    return;
  }

  // 2. Bat dau ket noi Capture moi
  HTTPClient captureHttp;
  String url = SERVER_URL + "/api/upload_raw";

  globalSecureClient.setInsecure();
  captureHttp.begin(globalSecureClient, url);

  captureHttp.addHeader("Content-Type", "application/octet-stream");
  captureHttp.addHeader("ngrok-skip-browser-warning", "true");
  captureHttp.addHeader("X-Device-ID", DEVICE_ID);
  captureHttp.addHeader("X-Frame-Width", String(camW));
  captureHttp.addHeader("X-Frame-Height", String(camH));
  captureHttp.addHeader("X-Frame-Format", "RGB565");
  captureHttp.setTimeout(10000); // Cho phep 10s cho anh nang

  Serial.println("[CAPTURE] Dang gui POST request...");
  int code = captureHttp.POST(sendBuf, camW * camH * 2);

  if (code == 200 || code == 201) {
    Serial.println("[CAPTURE] ✅ UPLOAD THANH CONG!");
    sendACK(cmdId, "OK", "Capture OK");
    frameCount++;
  } else {
    Serial.printf("[CAPTURE] ❌ Upload THAT BAI: %d\n", code);
    sendACK(cmdId, "ERROR", "HTTP " + String(code));
  }

  // 3. Xoa sach moi thu de giai phong RAM cho lan sau
  captureHttp.end();
  globalSecureClient.stop(); // Force stop socket
  vTaskDelay(200 / portTICK_PERIOD_MS);

  Serial.printf("[MEM] RAM sau upload: %d bytes\n", ESP.getFreeHeap());
}

// ========================= HEARTBEAT =========================

void sendHeartbeat() {
  if (!mqttClient.connected())
    return;

  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["device_type"] = "camera";
  doc["status"] = isStreaming ? "streaming" : "online";
  doc["ip_address"] = WiFi.localIP().toString();
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["uptime"] = millis() / 1000;
  doc["fw_version"] = FIRMWARE_VERSION;
  doc["stream_fps"] = isStreaming ? (int)streamFPS : 0;
  doc["frame_count"] = (long)frameCount;

  String output;
  serializeJson(doc, output);
  mqttClient.publish(TOPIC_HEARTBEAT, output.c_str());
}

// ========================= MQTT HELPERS =========================

void sendACK(String cmdId, String status, String message) {
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["cmd_id"] = cmdId;
  doc["status"] = status;
  doc["message"] = message;
  doc["timestamp"] = millis() / 1000;

  String output;
  serializeJson(doc, output);
  mqttClient.publish(TOPIC_ACK, output.c_str());
  Serial.printf("[ACK] %s: %s — %s\n", cmdId.c_str(), status.c_str(),
                message.c_str());
}

void sendLog(const char *level, const char *event, const char *message) {
  if (!mqttClient.connected())
    return;
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["level"] = level;
  doc["event"] = event;
  doc["message"] = message;
  doc["fw_version"] = FIRMWARE_VERSION;

  String output;
  serializeJson(doc, output);
  mqttClient.publish(TOPIC_LOG, output.c_str());
}
