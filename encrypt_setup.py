import json
from cryptography.fernet import Fernet
import os

# 파일 이름 정의
KEY_FILE = "secret.key"
JSON_FILE = "login_info.json"

def generate_key():
    """키를 생성하고 파일로 저장"""
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)
        print(f"✅ 새로운 키 파일('{KEY_FILE}')이 생성되었습니다.")
    else:
        print(f"ℹ️ 기존 키 파일('{KEY_FILE}')을 사용합니다.")

def load_key():
    """키 파일에서 키 읽기"""
    return open(KEY_FILE, "rb").read()

def encrypt_passwords():
    """JSON 파일을 읽어 비밀번호를 암호화"""
    key = load_key()
    fernet = Fernet(key)

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for user in data:
            # 1. 어떤 키가 비밀번호인지 찾기 ('password' 또는 'pw')
            target_key = None
            if 'password' in user:
                target_key = 'password'
            elif 'pw' in user:
                target_key = 'pw'
            
            # 비밀번호 키가 없으면 건너뜀
            if not target_key:
                print(f"⚠️ 경고: {user.get('name', 'Unknown')} 님의 정보에 비밀번호('pw' 또는 'password')가 없습니다.")
                continue

            current_pw = user[target_key]

            # 2. 이미 암호화된 것(gAAAA로 시작)은 건너뜀
            if current_pw.startswith("gAAAA"):
                print(f"ℹ️ {user.get('name', 'Unknown')}님의 비밀번호는 이미 암호화되어 있습니다.")
                continue
            
            # 3. 비밀번호 암호화 실행
            encrypted_pwd = fernet.encrypt(current_pw.encode())
            user[target_key] = encrypted_pwd.decode() # 바이트를 문자열로 변환하여 저장
            print(f"🔒 {user.get('name', 'Unknown')}님의 비밀번호 암호화 완료! (Key: {target_key})")

        # 저장
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("✅ 모든 작업이 완료되었습니다. 이제 work_manager.py를 실행하세요.")

    except FileNotFoundError:
        print(f"❌ '{JSON_FILE}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    generate_key()
    encrypt_passwords()