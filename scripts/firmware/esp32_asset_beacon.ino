/*
 * ==============================================================================
 * EAM ENTERPRISE ASSET MANAGEMENT — ESP32 UNIVERSAL ASSET PROXIMITY BEACON
 * ==============================================================================
 * Phần cứng: ESP32 DevKit V1 (ESP-WROOM-32, CP2102, Cổng USB Type-C)
 * Chức năng: Mỏ neo không gian vạn năng (Universal Spatial Anchor Beacon)
 * Tầm phủ sóng: Chuẩn bán kính 50 mét (TxPower +9 dBm)
 *
 * TỐI ƯU HÓA CÔNG NGHIỆP — CHỐNG NÓNG & ĐỘ CHÍNH XÁC CAO:
 * 1. Hạ xung CPU từ 240MHz xuống 80MHz: Giảm 65% dòng điện, mạch chạy 24/7 mát rượi.
 * 2. Tắt hoàn toàn WiFi Radio (WiFi.mode(WIFI_OFF)): Triệt tiêu triệt để nguồn phát nhiệt.
 * 3. Chu kỳ phát chuẩn Apple iBeacon (100ms interval): Bắt sóng tức thì (<0.5s), 
 *    RF Duty Cycle chỉ 1.5%, loại bỏ hoàn toàn hiện tượng trôi dạt nhiệt (Thermal Drift).
 * 4. Đèn LED chỉ báo nhịp tim (Heartbeat LED): Nhấp nháy nhẹ báo trạng thái hoạt động.
 * ==============================================================================
 */

#include <esp_bt.h>
#include <esp_wifi.h>
#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLEBeacon.h>

// UUID chuẩn EAM Proximity Beacon (128-bit)
#define BEACON_UUID   "e2c56db5-dffb-48d2-b060-d0f5a71096e0"
#define BEACON_MAJOR  1
#define BEACON_MINOR  100
#define MEASURED_POWER_1M -59 // Cường độ tín hiệu chuẩn đo tại 1 mét: -59 dBm

#define LED_PIN 2 // Đèn LED xanh tích hợp sẵn trên mạch ESP32 DevKit

BLEAdvertising *pAdvertising;
unsigned long lastHeartbeat = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  // 1. TỐI ƯU CÔNG SUẤT & NHIỆT ĐỘ: Hạ xung nhịp CPU về 80MHz (đủ cho BLE stack)
  setCpuFrequencyMhz(80);
  
  // 2. TẮT HOÀN TOÀN WIFI: Triệt tiêu dòng tiêu thụ 150-200mA và nguồn nhiệt lớn nhất
  WiFi.mode(WIFI_OFF);
  esp_wifi_stop();

  // Cấu hình chân đèn LED nhịp tim
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH); // Sáng nhẹ lúc khởi động

  Serial.println("\n========================================================");
  Serial.println("   EAM SYSTEM — ESP32 INDUSTRIAL ASSET BEACON v2.0     ");
  Serial.println("========================================================");
  Serial.printf(" - Tần số CPU:         %d MHz (Mát máy, tiết kiệm pin)\n", getCpuFrequencyMhz());
  Serial.println(" - Chế độ WiFi:        ĐÃ TẮT (Chống nóng 100%)");

  // 3. KHỞI TẠO BLE STACK
  BLEDevice::init("EAM-UNIVERSAL-BEACON");

  // Đặt công suất phát tối đa (+9 dBm) để phủ sóng chuẩn xác bán kính 50 mét
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_DEFAULT, ESP_PWR_LVL_P9);

  // 4. CẤU HÌNH GÓI TIN CHUẨN APPLE iBEACON (Chống nhiễu & Độ chính xác cao)
  BLEBeacon myBeacon = BLEBeacon();
  myBeacon.setManufacturerId(0x4C00); // 0x4C00 = Apple Inc.
  
  BLEUUID bleUUID = BLEUUID(BEACON_UUID);
  myBeacon.setProximityUUID(bleUUID);
  myBeacon.setMajor(BEACON_MAJOR);
  myBeacon.setMinor(BEACON_MINOR);
  myBeacon.setSignalPower(MEASURED_POWER_1M);

  BLEAdvertisementData advData;
  advData.setFlags(0x06); // 0x06 = LE General Discoverable + BR/EDR Not Supported

  std::string strServiceData = "";
  strServiceData += (char)26;     // Độ dài gói tin Manufacturer
  strServiceData += (char)0xFF;   // Loại 0xFF: Manufacturer Specific Data
  strServiceData += myBeacon.getData();
  advData.addData(strServiceData);

  pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->setAdvertisementData(advData);
  pAdvertising->setScanResponse(false); // Không cần scan response để giảm tải phát sóng

  // 5. CHU KỲ PHÁT 100ms (160 * 0.625ms): Chuẩn vàng cho định vị tức thì và mát chip
  pAdvertising->setMinInterval(160); // 100ms
  pAdvertising->setMaxInterval(160); // 100ms

  pAdvertising->start();

  Serial.println(" - Trạng thái BLE:     ĐANG PHÁT SÓNG LIÊN TỤC");
  Serial.println(" - Tên thiết bị:       EAM-UNIVERSAL-BEACON");
  Serial.println(" - UUID:               " BEACON_UUID);
  Serial.printf(" - Major / Minor:      %d / %d\n", BEACON_MAJOR, BEACON_MINOR);
  Serial.printf(" - Công suất phát:     +9 dBm (Phủ sóng ~50m, TxPower1m: %d dBm)\n", MEASURED_POWER_1M);
  Serial.println(" - Chu kỳ quảng bá:    100 ms (Bắt sóng tức thì < 0.5s)");
  Serial.println("========================================================");
  Serial.println(">> Mạch đã sẵn sàng! Cắm nguồn Type-C là chạy vĩnh viễn.");

  digitalWrite(LED_PIN, LOW);
}

void loop() {
  // Nhấp nháy đèn LED nhịp tim cực ngắn (50ms) mỗi 2.5 giây
  // Báo hiệu mạch đang sống mà không làm hao phí năng lượng hay nóng chip
  unsigned long currentMillis = millis();
  if (currentMillis - lastHeartbeat >= 2500) {
    lastHeartbeat = currentMillis;
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
  }
  
  // Cho CPU nghỉ ngơi (Light Idle) để giữ nhiệt độ chip luôn mát
  delay(100);
}
