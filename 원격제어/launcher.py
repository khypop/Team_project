import sys
import os
import urllib.parse
import ctypes

def run_launcher():
    # 1. 기본값 설정
    mode = "standard"
    
    # 2. 브라우저 인자 처리 (remote-connect://run?mode=standard)
    if len(sys.argv) > 1:
        try:
            raw_url = sys.argv[1]
            parsed_url = urllib.parse.urlparse(raw_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            extracted_mode = query_params.get("mode", ["standard"])[0]
            mode = extracted_mode.lower()
        except Exception:
            pass

    # 3. 고정 설치 경로 설정
    base_path = r"C:\remoteconnect"
    
    # 4. --onedir 빌드 구조에 따른 경로 매칭
    # 폴더 구조: C:\remoteconnect\gst_client\gst_client.exe 형태 가정
    if mode == "fsrcnn":
        # FSRCNN_Client 폴더 내의 실행 파일 호출
        target_folder = "fsrcnn_client"
        target_exe = "fsrcnn_client.exe"
    else:
        # gst_client 폴더 내의 실행 파일 호출
        target_folder = "gst_client"
        target_exe = "gst_client.exe"

    # 최종 경로 생성: C:\remoteconnect\gst_client\gst_client.exe
    full_path = os.path.join(base_path, target_folder, target_exe)

    # 5. 파일 존재 여부 확인 및 실행
    if os.path.exists(full_path):
        # working directory를 해당 폴더로 설정하여 DLL 참조 오류 방지
        os.chdir(os.path.join(base_path, target_folder))
        os.startfile(target_exe)
    else:
        ctypes.windll.user32.MessageBoxW(
            0, 
            f"파일을 찾을 수 없습니다.\n\n시도한 경로: {full_path}\n\n폴더 구조가 정확한지 확인하세요.", 
            "RemoteConnect Launcher Error", 
            16
        )

if __name__ == "__main__":
    run_launcher()