import pygetwindow as gw
import asyncio, json, socket, time
import signal
import threading
from pynput.keyboard import Key, Controller as KeyboardController, KeyCode
from pynput.mouse import Button, Controller as MouseController

#GStreamer 설정-------------------------
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
#--------------------------------------

import os
os.environ['GST_DEBUG'] = "3"
Gst.init(None)

# SEVER IP, PORT 설정
SEVER_IP = '0.0.0.0'
SERVER_PORT = 6000
#5000 TCP 영상 수신 포트
CLIENT_PORT = 5000

class ScreenCapture:
    def __init__(self, ip, port):
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

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.pipeline.set_state(Gst.State.PLAYING)

            self.loop = GLib.MainLoop()
            self.thread = threading.Thread(target=self.loop.run)
            self.thread.daemon = True
            self.thread.start()
        except Exception as e:
            print(f"파이프라인 생성 실패! 오류:\n{e}")

    def stop_capture(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            
        if self.loop:
            self.loop.quit()
            
class SocketServer:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.socket = None
        self.video_capture = None

    def start(self):
        thread = threading.Thread(target=self.connect)
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

                self.video_capture = ScreenCapture(addr[0], CLIENT_PORT)
                self.video_capture.start_capture()

                self.handle_client(conn)
            except Exception as e:
                print(f"소켓 연결 오류: {e}")
                break

    def handle_client(self, conn):
        buffer = ""
        while True:
            try:
                data = conn.recv(1024)
                if not data: break
                
                # 데이터가 뭉쳐서 올 수 있으므로 줄바꿈(\n)으로 분리
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    cmd, buffer = buffer.split('\n', 1)
                    self.execute_command(cmd)
                
            except Exception as e:
                print(f"제어 연결 끊김: {e}")
                break
        conn.close()

    def execute_command(self, cmd_str):
        try:
            parts = cmd_str.split(',')

            match parts:
                case ["MM", x, y]: 
                    self.mouse.position = (int(x), int(y))

                case ["MC", btn_name, state, x, y]:
                    button = Button.left if btn_name == 'left' else \
                             Button.right if btn_name == 'right' else Button.middle
                    
                    if state == 'D': self.mouse.press(button)
                    else: self.mouse.release(button)

                case ["KD", key_type, key_str]:
                    key = self._parse_key(key_type,key_str)
                    if key: self.keyboard.press(key)

                case ["KU", key_type, key_str]:
                    key = self._parse_key(key_type, key_str)
                    if key: self.keyboard.release(key)

                case _:
                    pass
                
        except Exception:
            pass # 너무 빠른 입력 에러는 무시

    #키보드 입력을 받아 처리하는 함수
    def _parse_key(self, key_type, key_str):
        if key_type == 'VK':
            return KeyCode.from_vk(int(key_str))
        elif key_type == 'SP':
            return getattr(Key, key_str.split('.')[1], None)
        return key_str.replace("'", "")

    def disconnect(self):
        if self.socket:
            self.socket.close()
            if self.video_capture:
                self.video_capture.stop_capture()

def main():
    socket_server = SocketServer()
    socket_server.start()
    
    try:
        while True:
            time.sleep(1) # 소켓
    except KeyboardInterrupt:
        print("\n프로그램 종료 요청")
    finally:
        socket_server.disconnect()

if __name__ == "__main__":
    #KeyboardInterrupt 핸들링
    #signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()