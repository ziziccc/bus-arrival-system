import requests
import os
import sys

try:
    from text_to_speech_rpi import speak
except ImportError:
    print("text_to_speech_rpi.py 파일을 찾을 수 없습니다.", file=sys.stderr)
    def speak(text, **kwargs): pass
    sys.exit(1)

BUS_NUMBER_FILE = "bus_number.txt"
USB_SPEAKER_KEYWORD = "USB"
BUS_ROUTE_IDS = {
    "5100":  "200000115", "7000":  "200000112",
    "1112":  "234000016", "M5107": "234001243"
}
STATION_ID  = "228000723"
STA_ORDER   = "56"
SERVICE_KEY = "fyVjph7SaBxYmvv2CF0Z%2B30SYBnR4MjVuWiH8sVdEtdYnj%2FbSb8KMK9WmxMnCMuNtBWgq2O%2B%2FLn21gZ2pSVDpw%3D%3D"

def get_single_bus_info(bus_number):
    if bus_number not in BUS_ROUTE_IDS:
        return f"{bus_number}번 버스는 지원되지 않는 노선입니다."

    route_id = BUS_ROUTE_IDS[bus_number]
    url = (
        "http://apis.data.go.kr/6410000/busarrivalservice/v2/getBusArrivalItemv2"
        f"?serviceKey={SERVICE_KEY}&stationId={STATION_ID}"
        f"&routeId={route_id}&staOrder={STA_ORDER}&format=json"
    )
    
    try:
        data = requests.get(url, timeout=10).json()
        item = data["response"]["msgBody"]["busArrivalItem"]
        predict_time = item.get("predictTime1")
        location_no  = item.get("locationNo1")
        
        if predict_time and location_no:
            return f"{bus_number}번 버스는 {predict_time}분 후 도착 예정이며, 남은 정류장은 {location_no}개 입니다."
        else:
            return f"{bus_number}번 버스의 실시간 도착 정보가 없습니다."
    except Exception as e:
        print(f"{bus_number}번 버스 정보 조회 실패: {e}", file=sys.stderr)
        return f"{bus_number}번 버스 정보를 가져오는 데 실패했습니다."

def main():
    buses_to_check = []
    
    if len(sys.argv) > 1:
        buses_to_check.append(sys.argv[1])
        print(f"단일 버스 조회 모드: {buses_to_check}")
    else:
        print("전체 버스 조회 모드")
        try:
            if not os.path.exists(BUS_NUMBER_FILE):
                speak("저장된 버스 정보가 없습니다.", speaker_keyword=USB_SPEAKER_KEYWORD)
                return
            
            with open(BUS_NUMBER_FILE, 'r', encoding='utf-8') as f:
                buses_to_check = [line.strip() for line in f if line.strip()]
            
            if not buses_to_check:
                speak("저장된 버스 정보가 없습니다.", speaker_keyword=USB_SPEAKER_KEYWORD)
                return

        except Exception as e:
            speak("버스 번호 파일을 읽는 데 실패했습니다.", speaker_keyword=USB_SPEAKER_KEYWORD)
            return

    all_info = []
    for bus in buses_to_check:
        info = get_single_bus_info(bus)
        all_info.append(info)

    if all_info:
        final_speech = " 그리고, ".join(all_info)
        print(f"{final_speech}")
        speak(final_speech, speaker_keyword=USB_SPEAKER_KEYWORD)

if __name__ == '__main__':
    main()

