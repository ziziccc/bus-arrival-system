#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>


#define CE_PIN   9
#define CSN_PIN 10


RF24 radio(CE_PIN, CSN_PIN);
const byte address[6] = "00001";


LiquidCrystal_I2C lcd(0x27, 16, 2);


struct NumberItem {
  String number;
  unsigned long tries;
  int successCount;    
};


#define SEND_INTERVAL 1000  
const int MAX_SUCCESS = 10; 


NumberItem sendList[10];
int sendListSize = 0;
int sendIndex    = 0;
unsigned long lastSendTime = 0;


void setup() {
  Serial.begin(115200);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("NRF24 TX READY");


  radio.begin();
  radio.setChannel(0x4C);
  radio.setDataRate(RF24_1MBPS);
  radio.setPALevel(RF24_PA_MIN);
  radio.setAutoAck(true);
  radio.openWritingPipe(address);
  radio.stopListening();


  Serial.println("Ready. Add bus numbers via Serial.");
}


void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() > 0 && sendListSize < 10) {
      bool exists = false;
      for (int i = 0; i < sendListSize; i++) {
        if (sendList[i].number.equals(input)) {
          exists = true;
          break;
        }
      }
      if (!exists) {
        sendList[sendListSize] = { input, 0, 0 };
        sendListSize++;
        Serial.print("Added bus: "); Serial.println(input);
      } else {
        Serial.print("Bus "); Serial.print(input); Serial.println(" already in list.");
      }
    }
  }


  unsigned long now = millis();
  if (sendListSize > 0 && now - lastSendTime >= SEND_INTERVAL) {
    NumberItem &item = sendList[sendIndex];
    bool ok = sendNumber(item.number);
    item.tries++;


    Serial.print("TX "); Serial.print(item.number);
    Serial.print(" (try "); Serial.print(item.tries);
    Serial.print(")  ACK "); Serial.println(ok ? "YES" : "NO");


    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(item.number);
    lcd.print(ok ? " ACK" : " NO");
    lcd.setCursor(0, 1);
    lcd.print("S:");
    lcd.print(item.successCount);
    lcd.print("/");
    lcd.print(MAX_SUCCESS);


    if (ok) { 
      item.successCount++;
      if (item.successCount >= MAX_SUCCESS) {
        Serial.print("ARRIVED:");
        Serial.println(item.number);
       
        removeNumberAt(sendIndex);
       
        if (sendIndex >= sendListSize) {
          sendIndex = 0;
        }
        lastSendTime = now;
        return;  
      }
    }


    sendIndex = (sendIndex + 1) % sendListSize;
    lastSendTime = now;
  }
}


bool sendNumber(const String &num) {
  char buf[32];
  num.toCharArray(buf, 32);
  for (int i = num.length(); i < 32; i++) {
    buf[i] = '\0';
  }
  return radio.write(buf, 32);
}


void removeNumberAt(int idx) {
  if (idx < 0 || idx >= sendListSize) return;
  for (int i = idx; i < sendListSize - 1; i++) {
    sendList[i] = sendList[i + 1];
  }
  sendListSize--;
}

