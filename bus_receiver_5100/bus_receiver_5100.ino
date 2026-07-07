#include "Arduino.h"
#include "Audio.h"
#include "SD.h"
#include "FS.h"
#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(4, 16); // CE, CSN
const byte address[] = "00001";

// microSD Card Reader connections
#define SD_CS      5
#define SPI_MOSI  23
#define SPI_MISO  19
#define SPI_SCK   18

// I2S Connections
#define I2S_DOUT  26
#define I2S_BCLK  27
#define I2S_LRC   25

#define LED_PIN   14      // LED 출력 핀
#define BUTTON_PIN  33    // 버튼 입력 핀 (내부 풀업 지원)

Audio audio;

bool repeatMode = false;      // 반복 재생 상태
bool lastButtonState = HIGH;  // 버튼 이전 상태(풀업 기준)
String mp3File = "/5100.mp3"; // 반복 재생할 mp3 파일명

char lastReceived[32] = {0};  // 마지막 수신값 저장
bool ledOn = false;           // LED 상태 플래그

void setup() {
  pinMode(SD_CS, OUTPUT);
  digitalWrite(SD_CS, LOW);

  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI);
  Serial.begin(115200);
  delay(500); // 시리얼 안정화

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  pinMode(BUTTON_PIN, INPUT_PULLUP); // 내부 풀업 사용

  if (radio.begin()) {
    Serial.println("nRF24L01 무선통신모듈 인식 성공!");
  } else {
    Serial.println("nRF24L01 무선통신모듈 인식 실패!");
    while (true);
  }

  radio.setPALevel(RF24_PA_HIGH);
  radio.openReadingPipe(1, address);
  radio.startListening();

  if (SD.begin(SD_CS)) {
    Serial.println("SD카드 인식 성공!");
  } else {
    Serial.println("SD카드 인식 실패!");
    while (true);
  }

  audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
  audio.setVolume(21);

  Serial.println("시스템 준비 완료!");
}

void loop() {
  // 버튼 입력 처리 (이벤트 감지)
  bool buttonState = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && buttonState == LOW) {
    Serial.println("버튼 눌림! (LED OFF & MP3 토글)");
    ledOn = false;
    digitalWrite(LED_PIN, LOW);
   
    // 반복 재생 모드 토글
    repeatMode = !repeatMode;
   
    if (repeatMode) {
      Serial.println("반복 재생 시작");
      if (!audio.isRunning()) {
        audio.connecttoFS(SD, mp3File.c_str());
      }
    } else {
      Serial.println("반복 재생 종료");
      audio.connecttoFS(SD, "/no_file.mp3"); // 존재하지 않는 파일 연결로 재생 중지
    }
  }
  lastButtonState = buttonState;

  // nRF24L01 수신 처리
  if (radio.available()) {
    char text[32] = {0};
    radio.read(&text, sizeof(text));
    strncpy(lastReceived, text, sizeof(lastReceived) - 1);
    lastReceived[sizeof(lastReceived) - 1] = '\0';
    Serial.print("수신 데이터: ");
    Serial.println(text);

    if (strcmp(text, "5100") == 0) {
      ledOn = true;
      digitalWrite(LED_PIN, HIGH);
    }
  } else {
    strncpy(lastReceived, "0", sizeof(lastReceived) - 1);
    lastReceived[sizeof(lastReceived) - 1] = '\0';
  }

  // 오디오 반복 재생 처리
  if (repeatMode) {
    if (!audio.isRunning()) {
      audio.connecttoFS(SD, mp3File.c_str());
    }
    audio.loop();
  } else {
    if (audio.isRunning()) {
      audio.loop();
    }
  }

  delay(10); // 아주 짧게!
}
