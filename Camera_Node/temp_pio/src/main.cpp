// =============================================================
// OV7670 (non-FIFO) Video on ST7735 TFT with ESP32 DevKit V1
// Based on: https://github.com/kobatan/OV7670-ESP32
// =============================================================
//
// ST7735 TFT: 128x160 pixel
// -> Dung QQVGA (160x120) de vua man hinh
// -> Voi ROTATION=1: man hinh ngang 160x128, anh 160x120 vua khit

// #define MODE QVGA   // 320x240 — QUA LON cho ST7735!
#define MODE QQVGA // 160x120 — Vua voi ST7735
// #define MODE QCIF   // 176x144 (crop)
// #define MODE QQCIF  //  88x72  (crop)

#define COLOR RGB565
// #define COLOR YUV422

#define ROTATION 1 // 0~3

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <Arduino.h>
#include <OV7670.h>
#include <SPI.h>
#include <Wire.h>

// OV7670 pins
// SSCB_SDA(SIOD) -> 21(ESP32)
// SSCB_SCL(SIOC) -> 22(ESP32)
// RESET          -> 3.3V
// PWDN           -> GND
// HREF           -> NC
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
                                  .xclk_freq_hz = 10000000, // XCLK 10MHz
                                  .ledc_timer = LEDC_TIMER_0,
                                  .ledc_channel = LEDC_CHANNEL_0};

// TFT ST7735 pins
#define TFT_CS 5
#define TFT_DC 16
#define TFT_RST 17
// SPI mac dinh ESP32: MOSI=23, SCK=18, MISO=19

Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);
OV7670 cam;
uint16_t *buf, w, h;

void setup() {
  setCpuFrequencyMhz(240);
  Serial.begin(115200);

  Wire.begin();
  Wire.setClock(400000);

  // Init TFT ST7735
  // Thu INITR_BLACKTAB truoc, neu mau bi lech thi doi sang:
  //   INITR_GREENTAB, INITR_REDTAB, INITR_MINI160x80
  tft.initR(INITR_BLACKTAB);
  tft.setRotation(ROTATION);
  tft.fillScreen(ST77XX_BLACK);

  Serial.println("TFT ST7735 initialized OK");

  // Init Camera
  esp_err_t err = cam.init(&cam_conf, MODE, COLOR);
  if (err != ESP_OK) {
    Serial.println("cam.init ERROR");
    tft.setCursor(4, 10);
    tft.setTextColor(ST77XX_RED);
    tft.setTextSize(1);
    tft.println("CAM INIT ERR!");
    while (1) {
      delay(1000);
    }
  }

  cam.setPCLK(2, DBLV_CLK_x4);
  cam.vflip(false);

  Serial.printf("cam MID = %X\n\r", cam.getMID());
  Serial.printf("cam PID = %X\n\r", cam.getPID());

  // Set resolution dimensions
  switch (MODE) {
  case QVGA:
    w = 320;
    h = 240;
    break;
  case QQVGA:
    w = 160;
    h = 120;
    break;
  case QCIF:
    w = 176;
    h = 144;
    break;
  case QQCIF:
    w = 88;
    h = 72;
    break;
  }

  Serial.printf("Resolution: %d x %d\n", w, h);
  Serial.println("Camera ready! Streaming to TFT...");
}

void loop() {
  for (uint16_t y = 0; y < h; y++) {
    buf = cam.getLine(y + 1);
    tft.drawRGBBitmap(0, y, buf, w, 1);
  }
}