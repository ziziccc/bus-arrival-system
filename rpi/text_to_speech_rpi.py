import os
import subprocess
from gtts import gTTS
import sys
import re

TTS_LANG = 'ko'
TTS_AUDIO_FILE = "temp_tts_output.mp3"

def get_speaker_device_name_by_keyword(keyword):
    if not keyword:
        print("스피커 키워드가 없어 시스템 기본 장치를 사용합니다.")
        return None
    try:
        result = subprocess.run(['aplay', '-l'], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        
        for line in lines:
            if keyword.lower() in line.lower():
                match = re.search(r'card (\d+).*device (\d+)', line)
                if match:
                    card_num, device_num = match.groups()
                    device_name = f"hw:{card_num},{device_num}"
                    print(f"스피커 장치 찾음: '{line.strip()}' -> ALSA 이름: {device_name}")
                    return device_name
        
        print(f"경고: 키워드 '{keyword}'를 포함하는 스피커를 찾지 못했습니다. 기본 장치를 시도합니다.", file=sys.stderr)
        return None # 못 찾으면 None 반환
    except FileNotFoundError:
        print("오류: 'aplay' 명령을 찾을 수 없습니다. alsa-utils가 설치되어 있는지 확인하세요.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"스피커 장치 검색 중 오류: {e}", file=sys.stderr)
        return None


def speak(text_to_speak, speaker_keyword="USB", block=True):
    if not text_to_speak or not text_to_speak.strip():
        return
    alsa_device = get_speaker_device_name_by_keyword(speaker_keyword)

    try:
        tts = gTTS(text=text_to_speak, lang=TTS_LANG, slow=False)
        tts.save(TTS_AUDIO_FILE)

        cmd = ["mpg123", "-q"]
        if alsa_device:
            cmd.extend(["-a", alsa_device])
        
        cmd.append(TTS_AUDIO_FILE)
        
        print(f"[TTS Helper] 다음 명령어로 재생 시도: {' '.join(cmd)}")
        if block:
            subprocess.run(cmd, check=True, timeout=30, capture_output=True, text=True)

    except subprocess.CalledProcessError as e:
        print("[TTS Helper] 치명적 오류: mpg123 실행 실패.", file=sys.stderr)
        print(f"  - 오류 내용: {e.stderr.strip()}", file=sys.stderr)
        print("스피커가 올바르게 연결되고 인식되었는지 확인하세요.", file=sys.stderr)
    except Exception as e:
        print(f"예외 발생: {e}", file=sys.stderr)
    finally:
        if os.path.exists(TTS_AUDIO_FILE):
            os.remove(TTS_AUDIO_FILE)

