import os
import sys
import time
import serial
import subprocess
import RPi.GPIO as GPIO

try:
    import pygame
    from text_to_speech_rpi import speak
    tts_enabled = True
except ImportError:
    def speak(text, **kwargs):
        pass
    tts_enabled = False

LED_PIN = 18
ROWS = [1, 12, 16, 20]
COLS = [13, 6, 5, 0]
KEYS_LAYOUT = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']]

BASE_DIR           = "/home/pi"
NUMBER_FILE        = os.path.join(BASE_DIR, "bus_number.txt")
FETCH_SPEAK_SCRIPT = os.path.join(BASE_DIR, "fetch_and_speak.py")
VOICE_SCRIPT       = os.path.join(BASE_DIR, "run_pipeline.sh")

send_list      = []
DEBOUNCE_DELAY = 0.3

def launch_and_wait(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd)

def init_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for r in ROWS: GPIO.setup(r, GPIO.OUT, initial=GPIO.LOW)
    for c in COLS: GPIO.setup(c, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)

def read_keypad():
    for r_pin in ROWS:
        GPIO.output(r_pin, GPIO.HIGH)
        for c_pin in COLS:
            if GPIO.input(c_pin) == GPIO.HIGH:
                while GPIO.input(c_pin): time.sleep(0.01)
                GPIO.output(r_pin, GPIO.LOW)
                return KEYS_LAYOUT[ROWS.index(r_pin)][COLS.index(c_pin)]
        GPIO.output(r_pin, GPIO.LOW)
    return None

def add_bus_number(new_number):
    if new_number not in send_list:
        send_list.append(new_number)
        with open(NUMBER_FILE, 'w', encoding='utf-8') as f:
            for bus in sorted(send_list): f.write(bus + '\n')
        return True
    return False

def remove_bus_number(bus_to_remove):
    if bus_to_remove in send_list:
        send_list.remove(bus_to_remove)
        with open(NUMBER_FILE, 'w', encoding='utf-8') as f:
            for bus in sorted(send_list): f.write(bus + '\n')
        speak(f"{bus_to_remove}번 버스 도착이 확인되었습니다.", speaker_keyword="USB")
        if not send_list: speak("모든 버스 탑승이 완료되었습니다.", speaker_keyword="USB")
    else: 
        pass

def update_led_status():
    if send_list: GPIO.output(LED_PIN, GPIO.HIGH)
    else: GPIO.output(LED_PIN, GPIO.LOW)

def sync_state_from_file():
    global send_list
    if os.path.exists(NUMBER_FILE):
        with open(NUMBER_FILE, 'r', encoding='utf-8') as f:
            send_list = sorted([line.strip() for line in f if line.strip()])
    else:
        send_list = []
    update_led_status() 

def cleanup_and_exit(ser):
    if tts_enabled: pygame.quit()
    if ser and ser.is_open: ser.close()
    GPIO.cleanup()
    sys.exit(0)

def main():
    global tts_enabled, send_list
    ser = None
    try:
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.05)
        time.sleep(2)
    except serial.SerialException as e:
        try: speak("시리얼 장치 연결을 확인해주세요.", speaker_keyword="USB")
        except: pass
        sys.exit(1)

    init_gpio()
    if tts_enabled:
        try:
            pygame.init()
            pygame.mixer.init()
        except Exception as e:
            print(f"{e}"); tts_enabled = False

    send_list.clear()
    if os.path.exists(NUMBER_FILE): os.remove(NUMBER_FILE)

    update_led_status()
    speak("키패드 사용이 가능합니다.", speaker_keyword="USB")

    input_string = ""
    last_key, last_time = None, 0

    try:
        while True:
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                if response.startswith("ARRIVED:"):
                    arrived_bus = response.split(':')[1]
                    remove_bus_number(arrived_bus)
                    update_led_status()

            key = read_keypad()
            now = time.time()
            if key and (key != last_key or now - last_time > DEBOUNCE_DELAY):
                if tts_enabled: 
                    if key.isdigit(): speak(key, speaker_keyword="USB")
                    elif key == 'A': speak("지우기", speaker_keyword="USB")
                    elif key == '*': speak("다시", speaker_keyword="USB")
                    elif key == '#': speak("엠", speaker_keyword="USB")
                    elif key == 'D': speak("음성 입력 모드로 전환합니다.", speaker_keyword="USB")
                
                if key.isdigit(): input_string += key
                elif key == '#': input_string += 'M'
                elif key == 'A': input_string = input_string[:-1]
                elif key == '*': input_string = ""
                elif key == 'B':
                    if not send_list: speak("조회할 버스가 없습니다.", speaker_keyword="USB")
                    else:
                        speak("등록된 모든 버스의 실시간 도착 정보를 조회합니다.", speaker_keyword="USB")
                        launch_and_wait(["python3", FETCH_SPEAK_SCRIPT], cwd=BASE_DIR)
                elif key == 'C': 
                    if not input_string: speak("입력된 버스 번호가 없습니다.", speaker_keyword="USB")
                    else:
                        if add_bus_number(input_string):
                            speak(f"{input_string}번 버스를 등록합니다.", speaker_keyword="USB")
                            update_led_status()
                            launch_and_wait(["python3", FETCH_SPEAK_SCRIPT, input_string], cwd=BASE_DIR)
                            ser.write((input_string + '\n').encode())
                            print(f"전송: {input_string}")
                        else: speak(f"{input_string}번 버스는 이미 등록되어 있습니다.", speaker_keyword="USB")
                        input_string = ""
                elif key == 'D':
                    launch_and_wait(["bash", VOICE_SCRIPT], cwd=BASE_DIR)
                    sync_state_from_file()
                
                last_key, last_time = key, now
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\n종료(Ctrl+C)")
    finally:
        cleanup_and_exit(ser)

if __name__ == "__main__":
    main()

