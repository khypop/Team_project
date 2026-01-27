import gi
import sys
import signal
import socket
import threading
import time
from pynput import keyboard, mouse

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

SERVER_IP = '127.0.0.1'
SERVER_PORT = 6000

class ControlSender:
    def __init__(self, ip, port=6000):
        self.ip = ip
        self.port = port
        self.sock = None
        self.active = False # ★ 안전장치: F4 누를 때만 전송
        self.last_move_time = 0

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip, self.port))
            print("✅ 제어 서버 연결 성공!")
            return True
        except Exception:
            print("❌ 제어 서버 연결 실패 (영상만 봅니다)")
            return False

    def send_data(self, message):
        if self.sock and self.active: # 활성화 상태일 때만 전송
            try:
                self.sock.sendall((message + '\n').encode('utf-8'))
            except:
                pass

    def start(self):
        if not self.connect(): return

        # 리스너 시작
        self.kb_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.ms_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click)
        self.kb_listener.start()
        self.ms_listener.start()

    def on_key_press(self, key):
        # ★ F4 키로 제어 모드 토글 (Toggle)
        if key == keyboard.Key.f4:
            self.active = not self.active
            status = "ON 🟢" if self.active else "OFF 🔴"
            print(f"\n[제어 모드] {status} (내 키보드/마우스가 서버로 전송됩니다)")
            return

        if self.active:
            key_data = key.char if hasattr(key, 'char') else str(key)
            self.send_data(f"KD,{key_data}")

    def on_key_release(self, key):
        if self.active:
            key_data = key.char if hasattr(key, 'char') else str(key)
            self.send_data(f"KU,{key_data}")

    def on_move(self, x, y):
        if self.active:
            current_time = time.time()
            if current_time - self.last_move_time > 0.03:
                self.send_data(f"MM,{int(x)},{int(y)}")
                self.last_move_time = current_time

    def on_click(self, x, y, button, pressed):
        if self.active:
            state = "D" if pressed else "U"
            btn = str(button).replace('Button.', '')
            self.send_data(f"MC,{btn},{state},{int(x)},{int(y)}")

def main():
    
    
    # 1. 제어 송신기 시작
    control = ControlSender(ip=SERVER_IP, port=SERVER_PORT)
    control.start()

    # 2. 영상 수신기 시작 (안정화 버전: latency=20)
    pipeline_str = """
        udpsrc port=5000 ! 
        application/x-rtp, media=video, clock-rate=90000, encoding-name=H264, payload=96 ! 
        rtpjitterbuffer latency=20 mode=0 do-lost=true ! 
        rtph264depay ! 
        h264parse ! 
        avdec_h264 ! 
        videoconvert ! 
        d3dvideosink sync=false
    """

    print(f"📺 [{SERVER_IP}] 영상 수신 시작...")
    print("👉 [F4] 키를 누르면 원격 제어(키보드/마우스)가 켜집니다!")
    
    try:
        pipeline = Gst.parse_launch(pipeline_str)
        
        # 에러 처리 버스
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", lambda bus, msg: print(f"⚠️ 에러: {msg.parse_error()[0]}") if msg.type == Gst.MessageType.ERROR else None)
        
        pipeline.set_state(Gst.State.PLAYING)
        loop = GLib.MainLoop()
        loop.run()
        
    except Exception as e:
        print(f"실행 실패: {e}")
    finally:
        pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()