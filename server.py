import pygetwindow as gw
import asyncio, json, socket, time
import signal
import threading
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController

#GStreamer 설정-------------------------
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
#--------------------------------------

import os
os.environ['GST_DEBUG'] = "3"


# SEVER IP, PORT 설정
SEVER_IP = '0.0.0.0'
SERVER_PORT = 6000
CLIENT_IP = '127.0.0.1'
CLIENT_PORT = 5000

class ScreenCapture:
    def __init__(self, ip, port):
        Gst.init(None)
        self.ip = ip
        self.port = port
        self.pipeline = None
        self.loop = None

    def start_capture(self):
        
        pipeline_str = f"""
            d3d11screencapturesrc show-cursor=true ! 
            d3d11convert ! 
            d3d11download ! 
            videoconvert ! 
            videoscale ! video/x-raw,width=1920,height=1080,format=NV12 ! 
            mfh264enc bitrate=2000 rc-mode=0 gop-size=30 low-latency=true quality-vs-speed=0 !
            rtph264pay config-interval=1 mtu=600 pt=96 ! 
            udpsink host={self.ip} port={self.port} sync=false async=false
        """
        print('start stream')
        # 파이프라인 구축 

        try:
            self.pipeline = Gst.parse_launch(pipeline_str) #파이프라인 객체 생성
            self.pipeline.set_state(Gst.State.PLAYING) #파이프라인 실행

            self.loop = GLib.MainLoop() #gstreamer이벤트 처리 루프 생성
            self.thread = threading.Thread(target=self.loop.run) #스레드에서 GStreamer 실행
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            print(f"파이프라인 생성 실패! 오류:\n{e}")

    def stop_capture(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL) #파이프라인 종료
            
        if self.loop:
            self.loop.quit() #메인 루프 종료
            
class SocketServer:
    def __init__(self, video_capture):
        self.mouse = MouseController() #마우스제어 객체
        self.keyboard = KeyboardController() #키보드 제어 객체
        self.socket = None
        self.video_capture = video_capture

    def start(self):
        thread = threading.Thread(target=self.connect) #TCP 서버를 백그다운드 스레드로 실행
        thread.daemon = True
        thread.start()

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((SEVER_IP, SERVER_PORT))
        self.socket.listen(1)

        while True:
            try:
                conn, addr = self.socket.accept()
                print(f"클라이언트 접속: {addr}")

                if self.video_capture:
                    self.video_capture.start_capture() #비디오 캡쳐 

                self.handle_client(conn)
            except Exception as e:
                print(f"소켓 연결 오류: {e}")
                break

    def handle_client(self, conn):
        buffer = ""
        while True:
            try:
                data = conn.recv(1024) #데이터 수신
                if not data: break
                
                # 데이터가 뭉쳐서 올 수 있으므로 줄바꿈(\n)으로 분리
                buffer += data.decode('utf-8') #문자열 버퍼에 누적
                while '\n' in buffer:
                    cmd, buffer = buffer.split('\n', 1) #명령을 줄 단위로 분리
                    self.execute_command(cmd) #명령 실행
                
            except Exception as e:
                print(f"제어 연결 끊김: {e}")
                break
        conn.close()

    def execute_command(self, cmd_str):
        try:
            parts = cmd_str.split(',') #명령을 쉼표 기준으로 분해

            match parts:
                case ["MM", x, y]: #MM=Mouse Move 
                    self.mouse.position = (int(x), int(y))

                case ["MC", btn_name, state, x, y]: #MC=Mouse click
                    button = Button.left if btn_name == 'left' else \
                             Button.right if btn_name == 'right' else Button.middle
                    # EX)[마우스클릭,왼쪽,D,300,400] <- 300,400 좌표에 왼쪽버튼 마우스 클릭
                    # (선택사항) 클릭할 때 위치 보정까지 하고 싶다면
                    # self.mouse.position = (int(x), int(y)) 
                    
                    if state == 'D': self.mouse.press(button)
                    else: self.mouse.release(button) #마우스 드래그지원 D=Down 

                case ["KD", key_str]: #key Down 키보드 누르기
                    key = self._parse_key(key_str) #문자열 키 pynpuy 객체
                    if key: self.keyboard.press(key)

                case ["KU", key_str]: #키보드 떼기 
                    key = self._parse_key(key_str)
                    if key: self.keyboard.release(key)

                case _:
                    pass
                
        except Exception:
            pass # 너무 빠른 입력 에러는 무시

    def _parse_key(self, key_str):
        if key_str.startswith('Key.'): 
            return getattr(Key, key_str.split('.')[1], None)
        return key_str.replace("'", "")

    def disconnect(self):
        if self.socket:
            self.socket.close()

def main():
    video = ScreenCapture(CLIENT_IP, CLIENT_PORT)
    socket_server = SocketServer(video)

    socket_server.start()
    
    try:
        while True:
            time.sleep(1) # 소켓
    except KeyboardInterrupt:
        print("\n프로그램 종료 요청")
        video.stop_capture()

if __name__ == "__main__":
    #KeyboardInterrupt 핸들링
    #signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()