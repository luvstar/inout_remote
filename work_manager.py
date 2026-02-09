import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import json
import os
import sys
import time
import threading
import serial # pip install pyserial
from datetime import datetime

# --- [추가] 암호화 라이브러리 ---
from cryptography.fernet import Fernet # pip install cryptography

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

# --- (1) 사용자 및 환경 설정 ---
LOGIN_URL = "https://gw.cubox.ai/#/login?logout=Y&lang=kr"
MAIN_PAGE_URL = "https://gw.cubox.ai/#/" 

# 버튼 XPath 설정
BUTTON_XPATH_START = "//button[contains(., '출근') or contains(@id, 'btn_start')]" 
BUTTON_XPATH_END = "//ul[@class='btns']//li[contains(text(), '퇴근')]"

# 시리얼 포트 설정
SERIAL_PORT = 'COM8' 
BAUD_RATE = 115200

# 파일 경로 설정
def get_script_directory():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        return os.path.dirname(os.path.abspath(__file__))

JSON_FILE = os.path.join(get_script_directory(), "login_info.json")
KEY_FILE = os.path.join(get_script_directory(), "secret.key") # [추가] 키 파일 경로

# --- (2) 로그 및 UI 헬퍼 함수 ---
def log_message(message):
    timestamp = datetime.now().strftime("[%H:%M:%S] ")
    full_msg = timestamp + message
    print(full_msg) # 콘솔 출력
    
    # UI 스레드 안전하게 업데이트
    try:
        log_text_area.config(state=tk.NORMAL)
        log_text_area.insert(tk.END, full_msg + "\n")
        log_text_area.see(tk.END)
        log_text_area.config(state=tk.DISABLED)
    except:
        pass

def load_users():
    if not os.path.exists(JSON_FILE):
        log_message(f"❌ 오류: {JSON_FILE} 파일이 없습니다.")
        return []
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log_message(f"❌ JSON 로드 실패: {e}")
        return []

# --- 암호화 관련 헬퍼 함수 ---
def load_key():
    """저장된 키 파일을 불러옵니다."""
    if not os.path.exists(KEY_FILE):
        log_message("❌ 'secret.key' 파일이 없습니다! encrypt_setup.py를 먼저 실행하세요.")
        return None
    try:
        return open(KEY_FILE, "rb").read()
    except Exception as e:
        log_message(f"❌ 키 파일 읽기 실패: {e}")
        return None

def decrypt_password(encrypted_password):
    """암호화된 비밀번호를 복호화합니다."""
    key = load_key()
    if key is None:
        return None
    
    f = Fernet(key)
    try:
        # 암호화된 텍스트가 문자열이면 바이트로 변환
        if isinstance(encrypted_password, str):
            encrypted_password = encrypted_password.encode()
            
        decrypted_password = f.decrypt(encrypted_password).decode()
        return decrypted_password
    except Exception as e:
        log_message(f"❌ 비밀번호 복호화 실패: {e}")
        log_message("ℹ️ 비밀번호가 평문인지, 혹은 키 파일이 맞는지 확인하세요.")
        return None

# --- (3) Selenium 자동화 로직 (액션 수행) ---
def perform_commute_action(action_type, user_info):
    """
    action_type: "START" (출근) or "END" (퇴근)
    user_info: dict
    """
    user_id = user_info.get('id')
    user_name = user_info.get('name', 'Unknown')
    
    # 비밀번호 복호화 처리
    # JSON 키가 'pw'일 수도 있고 'password'일 수도 있음 (호환성 확보)
    encrypted_pw = user_info.get('pw') or user_info.get('password')
    
    if not encrypted_pw:
        log_message(f"❌ {user_name}님의 비밀번호 정보가 없습니다.")
        return

    # 복호화 시도
    real_password = decrypt_password(encrypted_pw)
    
    if not real_password:
        log_message(f"⛔ {user_name}님의 비밀번호 복호화 실패로 작업을 중단합니다.")
        return

    action_name = "출근" if action_type == "START" else "퇴근"
    log_message(f"🚀 [{user_name}] {action_name} 프로세스 시작...")

    driver = None
    try:
        # 옵션 설정
        chrome_options = Options()
        chrome_options.add_argument("--headless") 
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        # 불필요한 로그 제거
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # 1. 로그인 페이지 접속
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 15)

        # 2. 로그인 시퀀스
        log_message("로그인 진행 중...")
        time.sleep(2)
        
        # ID 입력
        id_input = wait.until(EC.element_to_be_clickable((By.ID, "reqLoginId")))
        id_input.clear()
        id_input.send_keys(user_id)
        
        # '다음' 버튼 클릭 (있는 경우)
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., '다음')]")))
            next_button.click()
        except:
            pass 

        # PW 입력 (복호화된 비밀번호 사용)
        pw_input = wait.until(EC.element_to_be_clickable((By.ID, "reqLoginPw")))
        pw_input.clear()
        pw_input.send_keys(real_password) # [수정] real_password 사용
        
        # 로그인 버튼 클릭
        login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., '로그인')]")))
        login_button.click()
        
        # 3. 메인 대시보드 진입 대기
        time.sleep(2) 

        # ---------------------------------------------------------
        # [수정된 로직] 출근은 버튼 클릭 스킵, 퇴근은 버튼 클릭 필요
        # ---------------------------------------------------------
        if action_type == "END":
            # 퇴근(END)일 경우에만 '퇴근' 버튼을 찾아 클릭
            try:
                log_message(f"'{action_name}' 버튼 찾는 중...")
                target_xpath = BUTTON_XPATH_END
                
                # 버튼이 나타날 때까지 대기
                action_btn = wait.until(EC.element_to_be_clickable((By.XPATH, target_xpath)))
                time.sleep(1) # 안정성을 위한 대기
                
                # JS로 강제 클릭
                driver.execute_script("arguments[0].click();", action_btn)
                log_message(f"✅ {user_name}님 {action_name} 버튼 클릭 완료!")
                
            except Exception as e:
                log_message(f"⚠️ 퇴근 버튼 클릭 실패: {e}")

        else:
            # 출근(START)일 경우: 버튼 클릭 없이 바로 팝업 대기
            log_message(f"🚀 {user_name}님 로그인 성공. (출근 버튼 클릭은 건너뜁니다)")
            time.sleep(2) 

        # ---------------------------------------------------------
        # [공통 로직] 팝업 창 '확인' 버튼 클릭 (출근/퇴근 모두 적용)
        # ---------------------------------------------------------
        log_message("팝업 창 '확인' 버튼 대기 중...")
        try:
            # 1. '확인' 버튼이 뜰 때까지 최대 5초 대기
            confirm_xpath = "//button[contains(., '확인')]"
            
            confirm_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, confirm_xpath))
            )
            
            # 2. 확실하게 하기 위해 JS로 강제 클릭
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", confirm_btn)
            
            log_message(f"✅ {action_name} 확인 팝업 승인(클릭) 완료!")
            time.sleep(2.5)
        except Exception as e:
            # 팝업이 안 뜨는 경우 경고만 출력
            log_message(f"ℹ️ 확인 팝업이 없거나 감지되지 않음: {e}")

    except Exception as e:
        log_message(f"❌ 오류 발생: {e}")
    finally:
        if driver:
            driver.quit()
        log_message("브라우저 종료됨.")

# --- (4) 시리얼 통신 스레드 ---
def serial_monitor_thread():
    users = load_users()
    if not users:
        log_message("사용자 정보가 없어 시리얼 모니터링을 중단합니다.")
        return

    log_message(f"🔌 시리얼 포트({SERIAL_PORT}) 연결 시도 중...")
    
    ser = None
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        log_message(f"✅ 시리얼 포트 연결 성공! 데이터 수신 대기 중...")
        
        while True:
            if ser.in_waiting > 0:
                # 데이터 읽기 및 디코딩
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line: continue
                
                log_message(f"📥 수신된 데이터: {line}")
                
                # 프로토콜 파싱 (CMD:START:0)
                parts = line.split(':')
                if len(parts) >= 3 and parts[0] == "CMD":
                    command = parts[1]      # START or END
                    try:
                        user_idx = int(parts[2]) # 0, 1, 2...
                    except ValueError:
                        log_message("인덱스 파싱 오류")
                        continue

                    if user_idx < 0 or user_idx >= len(users):
                        log_message(f"잘못된 사용자 인덱스: {user_idx}")
                        continue
                    
                    target_user = users[user_idx]
                    
                    # 작업을 스레드로 분리하여 시리얼 수신이 멈추지 않도록 함
                    t = threading.Thread(target=perform_commute_action, args=(command, target_user))
                    t.start()
                    
                    # 중복 실행 방지를 위한 약간의 딜레이
                    time.sleep(1)

            time.sleep(0.1) # CPU 점유율 방지

    except serial.SerialException as e:
        log_message(f"❌ 시리얼 포트 오류: {e}")
        log_message("포트 설정(SERIAL_PORT)을 확인하거나 장치가 연결되었는지 확인하세요.")
    except Exception as e:
        log_message(f"예기치 않은 오류: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()

# --- (5) UI 구성 (Tkinter) ---
def start_serial_thread():
    # 스레드 시작
    t = threading.Thread(target=serial_monitor_thread, daemon=True)
    t.start()

# UI 설정
BG_COLOR = "#2E2E2E"
TEXT_COLOR = "#EAEAEA"
APP_FONT = ("Malgun Gothic", 10)

window = tk.Tk()
window.title("STM32 원격 출퇴근 제어기 (보안 모드)")
window.geometry("500x400")
window.config(bg=BG_COLOR)

# 타이틀
lbl_title = tk.Label(window, text="STM32 Secure Automation Controller", font=("Malgun Gothic", 14, "bold"), bg=BG_COLOR, fg="#007ACC")
lbl_title.pack(pady=10)

# 상태 설명
lbl_info = tk.Label(window, text=f"연결 포트: {SERIAL_PORT} | 속도: {BAUD_RATE}", font=APP_FONT, bg=BG_COLOR, fg="#AAAAAA")
lbl_info.pack(pady=5)

# 로그창
log_text_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=APP_FONT, bg="#1E1E1E", fg=TEXT_COLOR, height=15)
log_text_area.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

# 시작 시 자동으로 시리얼 스레드 실행
window.after(100, start_serial_thread)

window.mainloop()