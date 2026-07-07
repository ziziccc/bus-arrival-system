#!/bin/bash
# run_pipeline.sh 

cd "$(dirname "$0")"
echo "--- run_pipeline.sh 시작됨 - $(date) ---"

LED_PIN = 18
SYSFS_GPIO="/sys/class/gpio"

echo
echo "음성인식 모듈(speech_to_text_rpi.py) 실행 중..."

OUTPUT=$(python3 speech_to_text_rpi.py)
PY_EXIT_CODE=$? 

if [ $PY_EXIT_CODE -ne 0 ]; then
    echo "[오류] 음성인식 모듈이 오류와 함께 종료되었습니다."
    exit 1
fi

CONFIRMED_BUS=$(echo "$OUTPUT" | grep "CONFIRMED_BUS:" | cut -d':' -f2)

if [ -z "$CONFIRMED_BUS" ]; then
    echo "[오류] 음성인식 결과에서 최종 버스 번호를 파싱하지 못했습니다."
    echo "--- 파이썬 스크립트 전체 출력 ---"
    echo "$OUTPUT"
    echo "---------------------------------"
    exit 1
fi

echo "음성인식으로 확인된 번호: $CONFIRMED_BUS"

echo
echo "아두이노우노로 시리얼 송신 중..."
SERIAL_PORT="/dev/ttyACM0"
BAUD_RATE=115200
echo -e "${CONFIRMED_BUS}\n" > "$SERIAL_PORT"
if [ $? -eq 0 ]; then
    echo "[시리얼 송신 성공] $CONFIRMED_BUS -> $SERIAL_PORT"
else
    echo "[시리얼 송신 실패] $CONFIRMED_BUS"
fi

echo "[LED 깜빡임 시작]"
if [ ! -d "$SYSFS_GPIO/gpio$LED_PIN" ]; then
    echo "$LED_PIN" > "$SYSFS_GPIO/export"
    sleep 0.1
    echo "out" > "$SYSFS_GPIO/gpio$LED_PIN/direction"
fi

echo "1" > "$SYSFS_GPIO/gpio$LED_PIN/value"
sleep 0.2
echo "0" > "$SYSFS_GPIO/gpio$LED_PIN/value"
echo "[LED 깜빡임 완료]"


echo
echo "확인된 버스($CONFIRMED_BUS) 정보 처리 요청..."
python3 fetch_and_speak.py "$CONFIRMED_BUS"

if [ $? -ne 0 ]; then
    echo "[오류] 정보 처리 모듈에서 오류가 발생했습니다."
fi
echo "정보 처리 모듈 완료."

echo
echo "--- 모든 파이프라인 작업 완료! ---"


