/*
 =============================================================================
 GEOGUARD AI — OFF-GRID HIGHWAY LANDSLIDE RECEIVER GATEWAY
 Target Hardware: ESP32 Dev Module + NRF24L01+ Wireless Transceiver
 Matches: GeoGuard_Transmitter.ino (Channel 100, Address "LAND1", 1MBPS, 32B)
 =============================================================================
 SPI PINOUT (ESP32 VSPI):
   - MOSI: GPIO 23
   - MISO: GPIO 19
   - SCK:  GPIO 18
   - CSN:  GPIO 5
   - CE:   GPIO 4
   - VCC:  3.3V (Use dedicated 3.3V with 10uF capacitor across VCC-GND)
   - GND:  GND
 =============================================================================
*/

#include <SPI.h>
#include <RF24.h>
#include <math.h>

// NRF24L01: CE = Pin 4, CSN = Pin 5
RF24 radio(4, 5);
const byte address[6] = "LAND1";

// Exactly 32 bytes matching Transmitter struct
struct SensorData {
  int rain;
  int soil;
  int vibration;
  float acceleration;
  float tilt;
  float temperature;
  float humidity;
  bool landslide;
};

SensorData data;
unsigned long packetCount = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  // VSPI Bus for ESP32: SCK=18, MISO=19, MOSI=23, SS=5
  SPI.begin(18, 19, 23, 5);

  if (!radio.begin()) {
    Serial.println("FATAL: NRF24L01 hardware not detected! Check 3.3V/GND/SPI wiring.");
    while (true) delay(1000);
  }

  // Exact matching radio parameters from Transmitter:
  radio.setChannel(100);
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_LOW);
  radio.setAutoAck(false);
  radio.setPayloadSize(sizeof(data)); // 32 bytes
  radio.openReadingPipe(1, address);
  radio.startListening();

  Serial.println("==================================================");
  Serial.println("GEOGUARD RECEIVER READY — MATCHED TO TRANSMITTER");
  Serial.println("Listening on Channel: 100 | Address: LAND1 (1MBPS)");
  Serial.println("==================================================");
}

void loop() {
  if (radio.available()) {
    radio.read(&data, sizeof(data));
    packetCount++;

    // Safe calibrations:
    // Soil % VWC: ESP32 12-bit ADC (Air ~ 4095 = 0%, Wet Soil ~ 1200 = 100%)
    float soil_pct = constrain(((4095.0 - (float)data.soil) / 2895.0) * 100.0, 0.0, 100.0);

    // Rain mm/h: Optical or tipping gauge ADC to mm/h
    float rain_mmh = constrain(((4095.0 - (float)data.rain) / 2895.0) * 50.0, 0.0, 50.0);

    // Vibration PGA:
    float vib_g = (data.vibration == 1 || data.vibration == HIGH) ? 0.85 : 0.02;

    // Tilt sanity:
    float tilt_deg = data.tilt;
    if (isnan(tilt_deg) || isinf(tilt_deg) || tilt_deg < -90.0 || tilt_deg > 90.0) {
      tilt_deg = 60.0;
    }

    // Temp sanity:
    float temp_c = data.temperature;
    if (isnan(temp_c) || temp_c < -40.0 || temp_c > 85.0) {
      temp_c = 22.0;
    }

    // 1. Direct atomic packet for GeoGuard PC Dashboard (CSV format)
    Serial.print("GEOGUARD,");
    Serial.print(soil_pct, 1); Serial.print(",");
    Serial.print(temp_c, 1); Serial.print(",");
    Serial.print(tilt_deg, 2); Serial.print(",");
    Serial.print(vib_g, 2); Serial.print(",");
    Serial.println(rain_mmh, 1);

    // 2. Multi-line stream for Arduino Serial Monitor
    Serial.println("\n--- RECEIVED SENSOR DATA ---");
    Serial.print("Packet #: "); Serial.println(packetCount);
    Serial.print("Rain: "); Serial.println(data.rain);
    Serial.print("Soil moisture: "); Serial.println(data.soil);
    Serial.print("Vibration: "); Serial.println(data.vibration);
    Serial.print("Acceleration: "); Serial.print(data.acceleration, 2); Serial.println(" g");
    Serial.print("Tilt: "); Serial.print(tilt_deg, 2); Serial.println(" degrees");
    Serial.print("Temperature: "); Serial.print(temp_c, 1); Serial.println(" C");
    Serial.print("Humidity: "); Serial.print(data.humidity, 1); Serial.println(" %");
    Serial.print("Landslide: "); Serial.println(data.landslide ? "WARNING" : "NORMAL");
    Serial.print("Status: "); Serial.println(data.landslide ? "LANDSLIDE WARNING" : "NORMAL");
    Serial.println("----------------------------");
  }
}
