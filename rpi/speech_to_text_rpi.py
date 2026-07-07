import pyaudio
from google.cloud import speech
import re
import time
import os
import sys

try:
    from text_to_speech_rpi import speak
except ImportError:
    print("text_to_speech_rpi.py 파일을 찾을 수 없습니다.", file=sys.stderr)
    def speak(text, **kwargs): pass

KEY_FILE_PATH = "/home/pi/ultimate-result-459908-h8-a9fcaceeb565.json"
USB_SPEAKER_KEYWORD = "USB"
USB_MIC_KEYWORD     = "USB"
FORMAT, CHANNELS, RATE, CHUNK = pyaudio.paInt16, 1, 48000, 1024
MAIN_RECORD_SECONDS, CONFIRM_RECORD_SECONDS = 3, 3
kor2num = { '공': '0', '영': '0', '일': '1', '이': '2', '삼': '3', '사': '4', '오': '5', '육': '6', '칠': '7', '팔': '8', '구': '9' }
kor_syllable_to_letter = { "에이": "A", "비": "B", "씨": "C", "디": "D", "이": "E", "에프": "F", "지": "G", "에이치": "H", "아이": "I", "제이": "J", "케이": "K", "엘": "L", "엠": "M", "엔": "N", "오": "O", "피": "P", "큐": "Q", "알": "R", "에스": "S", "티": "T", "유": "U", "브이": "V", "더블유": "W", "엑스": "X", "와이": "Y", "제트": "Z" }

def log_and_speak(message, log_prefix="[STT 안내]"):
    print(f"{log_prefix} {message}")
    speak(message, speaker_keyword=USB_SPEAKER_KEYWORD)

def add_bus_number(new_number, file_path):
    bus_set = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            bus_set = {line.strip() for line in f if line.strip()}
    
    bus_set.add(new_number)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        for bus in sorted(list(bus_set)):
            f.write(bus + '\n')
    print(f"  ▶ {file_path}에 {new_number} 추가/갱신 완료. 현재 목록: {sorted(list(bus_set))}")


def get_microphone_device_index_stt(p_instance, keyword):
    try:
        for i in range(p_instance.get_device_count()):
            dev_info = p_instance.get_device_info_by_index(i)
            if keyword.lower() in dev_info.get('name', '').lower() and dev_info.get('maxInputChannels', 0) >= CHANNELS:
                print(f"STT: 마이크 장치 찾음: {dev_info['name']} (인덱스: {i})"); return i
    except Exception as e: print(f"STT 마이크 검색 오류: {e}", file=sys.stderr)
    print(f"STT 경고: '{keyword}' 마이크를 찾지 못했습니다.", file=sys.stderr)
    try:
        default_info = p_instance.get_default_input_device_info()
        print(f"STT: 기본 입력 장치 사용: {default_info['name']} (인덱스: {default_info['index']})"); return default_info['index']
    except Exception: return None

def _process_korean_segment(segment_text):
    processed_chars, i, n = [], 0, len(segment_text)
    while i < n:
        found_char = False
        for kor_syl, letter in sorted(kor_syllable_to_letter.items(), key=lambda item: len(item[0]), reverse=True):
            if segment_text[i:].startswith(kor_syl):
                processed_chars.append(letter); i += len(kor_syl); found_char = True; break
        if found_char: continue
        if segment_text[i] in kor2num:
            processed_chars.append(kor2num[segment_text[i]]); i += 1; found_char = True
        if found_char: continue
        char_upper = segment_text[i].upper()
        if 'A' <= char_upper <= 'Z' or '0' <= char_upper <= '9':
            processed_chars.append(char_upper); i += 1; found_char = True
        if not found_char: i += 1
    return "".join(processed_chars)

def extract_bus_num(text):
    if not text: return ""
    processed_text = re.sub(r'\s+', '', text.upper().replace("번", "").replace("버스", "").strip())
    if not processed_text: return ""
    match = re.fullmatch(r'([A-Z])?(\d{1,5})(?:-(\d{1,2}))?', processed_text)
    if match:
        bus_str = (match.group(1) or "") + match.group(2) + (("-" + match.group(3)) if match.group(3) else "")
        return bus_str
    segments = [_process_korean_segment(s) for s in processed_text.split("다시") if s and _process_korean_segment(s)]
    if not segments: return ""
    final_bus_num = segments[0]
    if len(segments) > 1 and re.fullmatch(r'\d+', segments[0]) and re.fullmatch(r'\d+', segments[1]):
        final_bus_num += "-" + segments[1]
    if not re.search(r'\d', final_bus_num): return ""
    if re.fullmatch(r'[A-Z]?\d{1,5}(?:-\d{1,2})?', final_bus_num) and len(final_bus_num) <= 8:
        return final_bus_num
    return ""

def record_audio_pyaudio(duration_seconds):
    p_rec = pyaudio.PyAudio(); mic_idx = get_microphone_device_index_stt(p_rec, USB_MIC_KEYWORD)
    if mic_idx is None: p_rec.terminate(); return None
    stream_rec = None; frames = []
    try:
        stream_rec = p_rec.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK, input_device_index=mic_idx)
        print("STT: 마이크 녹음 시작..."); [frames.append(stream_rec.read(CHUNK, exception_on_overflow=False)) for _ in range(0, int(RATE / CHUNK * duration_seconds))]; print("STT: 녹음 완료.")
        return b''.join(frames)
    except Exception as e: print(f"STT: PyAudio 녹음 중 오류: {e}", file=sys.stderr); return None
    finally:
        if stream_rec: stream_rec.stop_stream(); stream_rec.close()
        if p_rec: p_rec.terminate()

def recognize_google_cloud(audio_data):
    if not audio_data: return None
    try:
        client = speech.SpeechClient.from_service_account_json(KEY_FILE_PATH)
        audio_input = speech.RecognitionAudio(content=audio_data)
        config = speech.RecognitionConfig(encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, sample_rate_hertz=RATE, language_code="ko-KR")
        print("STT: Google STT 서버로 음성 변환 요청 중...")
        response = client.recognize(config=config, audio=audio_input)
        return response.results[0].alternatives[0].transcript if response.results else None
    except Exception as e: print(f"STT: Google STT API 오류: {e}", file=sys.stderr); return None

def listen_for_confirmation():
    speak("네 또는 아니오로 답해주세요.", speaker_keyword=USB_SPEAKER_KEYWORD, block=False)
    audio_confirm = record_audio_pyaudio(CONFIRM_RECORD_SECONDS)
    if not audio_confirm: return None
    text_confirm = recognize_google_cloud(audio_confirm)
    if text_confirm:
        print(f"STT: 확인 응답 인식 결과 :  \"{text_confirm}\"")
        positive = ["네", "예", "응", "맞아", "오케이", "확인", "어", "그래"]
        negative = ["아니", "아니요", "틀려", "다시", "취소"]
        if any(p in text_confirm for p in positive): return True
        if any(n in text_confirm for n in negative): return False
    return None

def main():
    confirmed_bus_number = None
    log_and_speak("버스 번호를 말씀해주세요.")
    while confirmed_bus_number is None:
        audio_main = record_audio_pyaudio(MAIN_RECORD_SECONDS)
        if not audio_main:
            log_and_speak("음성 녹음에 실패했습니다. 다시 시도합니다."); time.sleep(1); continue
        text_main = recognize_google_cloud(audio_main)
        if not text_main:
            log_and_speak("죄송합니다, 음성을 알아듣지 못했습니다. 다시 말씀해주세요."); continue
        print(f"STT: 전체 음성 인식 결과 \"{text_main}\"")
        bus_number_candidate = extract_bus_num(text_main)
        if not bus_number_candidate:
            log_and_speak("버스 번호를 찾지 못했습니다. 다시 말씀해주세요."); continue
        print(f"STT: 버스번호 추출 {bus_number_candidate}")
        confirmation_message = f"{bus_number_candidate}번 버스, 맞으신가요?"
        log_and_speak(confirmation_message)
        confirmation_result = listen_for_confirmation()
        if confirmation_result is True:
            confirmed_bus_number = bus_number_candidate
            log_and_speak(f"{confirmed_bus_number}번 버스로 확인되었습니다.")
        elif confirmation_result is False:
            log_and_speak("알겠습니다. 버스 번호를 다시 말씀해주세요.")
        else:
            log_and_speak("죄송합니다. 답변을 제대로 듣지 못했습니다. 다시 말씀해주세요.")
    
    if confirmed_bus_number:
        add_bus_number(confirmed_bus_number, 'bus_number.txt')
        log_and_speak(f"{confirmed_bus_number} 번이 목록에 추가되었습니다.", log_prefix="[STT 최종 결과]")
        print(f"CONFIRMED_BUS:{confirmed_bus_number}")
    else:
        log_and_speak("오류가 발생하여 버스 번호를 확인하지 못했습니다.", log_prefix="[STT 오류]")
        sys.exit(1) # 오류 발생 시 0이 아닌 코드로 종료

if __name__ == "__main__":
    if not os.path.exists(KEY_FILE_PATH):
        error_msg = f"치명적 오류: 서비스 계정 키 파일({KEY_FILE_PATH})을 찾을 수 없습니다."
        print(error_msg, file=sys.stderr)
        if 'speak' in globals():
            speak("시스템 설정에 문제가 있어 음성 인식을 시작할 수 없습니다.", speaker_keyword=USB_SPEAKER_KEYWORD)
        exit(1)
    
    main()

