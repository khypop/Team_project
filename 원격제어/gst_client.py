import gi
import json
import asyncio
import websockets
import time
from pynput import mouse, keyboard
import dns.resolver
import os
import certifi
import ssl
import threading
import tkinter as tk
from tkinter import ttk

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')

from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)



class WebRTCClient:
    def __init__(self,gui):
        self.gui = gui
        self.pipe_str = (
            "webrtcbin name=recv bundle-policy=max-bundle "
            "stun-server=stun://stun.l.google.com:19302 "
            "decodebin name=dbin ! videoconvert ! autovideosink sync=false"
        )
        self.pipeline = Gst.parse_launch(self.pipe_str)
        self.webrtc = self.pipeline.get_by_name("recv") #webrtc 핸들
        self.data_channel = None #서버에서 연 데이터 채널 저장
        self.is_open = False #데이터 채널 오픈 여부 
        self.last_move_time= 0 
        self.control_active = False

    async def get_signaling_url(self):
        domain = "remote-system.duckdns.org"
        self.gui.update_status(f"📡 {domain}에서 시그널링 서버 주소 찾는 중...","orange")
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '1.1.1.1'] # 구글 DNS 사용
            answers = resolver.resolve(domain, "TXT")
            for rdata in answers:
                url = str(rdata).strip('"')
                if "wss://" in url:
                    self.gui.update_status(f"✅ 연결 주소 획득: {url}","orange")
                    return url
        except Exception as e:
            self.gui.update_status(f"❌ 주소 조회 실패: {e}","red")
        return None
    
    async def run(self):
        while True:
            try:
                self.loop = asyncio.get_running_loop()
                self.url= await self.get_signaling_url()
                ssl_context=ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                self.conn = await websockets.connect(self.url,ssl=ssl_context)
                await self.conn.send(json.dumps({"type": "register", "id": "client"}))
                #ice 후보 생성 시 호출 및 데이터 채널 수신  
                self.webrtc.connect("on-ice-candidate", self.on_ice_candidate)
                self.webrtc.connect("pad-added", self.on_pad_added)
                self.webrtc.connect("on-data-channel", self.on_data_channel)

                self.pipeline.set_state(Gst.State.PLAYING)
                self.gui.update_status("🚀 연결성공! 클라이언트에서 서버 연결 대기 중...","green")

                async for message in self.conn:
                    msg = json.loads(message)
                    if msg["type"] == "offer": #SDP offer 수신 
                        await self.handle_offer(msg["sdp"])
                    elif msg["type"] == "candidate": #ice 후보 추가 
                        self.webrtc.emit("add-ice-candidate", msg["sdpMLineIndex"], msg["candidate"])
            except Exception as e:
                self.gui.update_status("연결 오류 3초후에 재시도","red")
                await asyncio.sleep(3)

    def on_data_channel(self, webrtc, channel):
        self.data_channel = channel #데이터 채널 저장 
        channel.connect("on-open", self.on_channel_open) #데이터 채널 활성화 감지
 
    def on_channel_open(self, channel):
        self.gui.update_status("🔓 원격 제어 활성화","green")
        self.is_open = True  # 데이터 채널 오픈 키보드/마우스 제어 가능 
        self.start_listeners()

    def start_listeners(self):
        self.control_active= False
        
        # 마우스 이동 및 클릭
        def on_move(x, y):
            cur=time.time() 
            if self.is_open and self.control_active and (cur-self.last_move_time > 0.02):
                self.send_ctrl({"type": "mousemove", "x": int(x), "y": int(y)})
                self.last_move_time= cur

        def on_click(x, y, button, pressed):
            if self.is_open and self.control_active:
                btn = 'left' if button == mouse.Button.left else 'right'
                action="mousedown" if pressed else "mouseup"
                self.send_ctrl({"type": action, "x":int(x), "y":int(y),"button":btn})
        
        def on_scroll(x,y,dx,dy):
            if self.is_open and self.control_active:
                self.send_ctrl({"type":"mousescroll","dx":dx,"dy":dy})

        def on_press(key):
            if key == keyboard.Key.f12:
                # print("원격제어 종료(F12)")
                # self.pipeline.set_state(Gst.State.NULL)
                # self.key_listener.stop()
                # self.mouse_listener.stop()
                os._exit(0)
                # return False
            
            if key == keyboard.Key.f4:
                self.control_active = not self.control_active
                status = "활성화" if self.control_active else "비활성화"
                self.gui.update_mode(self.control_active)
                key_mouse_listener()
                return False
            send_key_event(key,"keydown")
        
        def on_release(key):
            if key == keyboard.Key.f4:
                return
            send_key_event(key,"keyup")

        # 키보드 입력
        def send_key_event(key,action):
            if self.is_open and self.control_active:
                try:
                    if hasattr(key,'char') and key.char:
                        k=key.char
                    elif hasattr(key,'vk'):
                        if key.vk==21: k='hangul'
                        elif key.vk==25: k='hanja'
                        else: k= key.name
                    else:
                        k= key.name
                    self.send_ctrl({"type": action, "key":k})
                except: pass

        def key_mouse_listener():
            if hasattr(self,'key_listener'):
                self.key_listener.stop()
            if hasattr(self,'mouse_listener'):
                self.mouse_listener.stop()

            is_suppress= self.control_active

            self.mouse_listener = mouse.Listener(
                on_move=on_move, on_click=on_click, on_scroll=on_scroll,
                suppress=is_suppress, daemon=True)
            
            self.key_listener = keyboard.Listener(
                on_press=on_press, on_release=on_release,
                suppress=is_suppress, daemon=True)
            
            self.mouse_listener.start()
            self.key_listener.start()

        # 최초 리스너 가동
        key_mouse_listener()


    def send_ctrl(self, payload):
        if self.data_channel:
            self.data_channel.emit("send-string", json.dumps(payload))
    # 영상 패드 연결 
    def on_pad_added(self, element, pad):
        if pad.direction != Gst.PadDirection.SRC: return
        decodebin = self.pipeline.get_by_name("dbin")
        sink_pad = decodebin.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)
    #offer 처리 
    async def handle_offer(self, sdp_text):
        res, sdp = GstSdp.SDPMessage.new()
        GstSdp.SDPMessage.parse_buffer(sdp_text.encode(), sdp)
        offer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdp)
        self.webrtc.emit("set-remote-description", offer, None)
        promise = Gst.Promise.new_with_change_func(self.on_answer_created)
        self.webrtc.emit("create-answer", None, promise) #offer에 대한 answer생성 요청
    #answer 생성 완료 및 answer 전송 
    def on_answer_created(self, promise):
        reply = promise.get_reply()
        answer = reply.get_value("answer")
        self.webrtc.emit("set-local-description", answer, None)
        msg = {"type": "answer", "target": "server", "sdp": answer.sdp.as_text()}
        asyncio.run_coroutine_threadsafe(self.conn.send(json.dumps(msg)), self.loop)

    def on_ice_candidate(self, element, mline, candidate):
        msg = {"type": "candidate", "target": "server", "sdpMLineIndex": mline, "candidate": candidate}
        asyncio.run_coroutine_threadsafe(self.conn.send(json.dumps(msg)), self.loop)

class ClientGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Remote system message")
        self.root.geometry("500x250")
        self.root.attributes("-topmost",True)

        self.status_var = tk.StringVar(value="대기중...")
        self.mode_var = tk.StringVar(value="제어:비활성화(F4)")

        tk.Label(self.root,text="[상태]",font=("Malgun gothic",9)).pack(pady=5)
        self.status_label = tk.Label(self.root, textvariable=self.status_var, font=("Malgun Gothic", 10, "bold"))
        self.status_label.pack()

        self.mode_label = tk.Label(self.root, textvariable=self.mode_var, font=("Malgun Gothic", 10))
        self.mode_label.pack(pady=10)

        tk.Button(self.root, text="종료 (F12)", command=lambda: os._exit(0), bg="red", fg="white").pack()

    def update_status(self, text, color):
        self.status_var.set(text)
        self.status_label.config(fg=color)

    def update_mode(self, active):
        if active:
            self.mode_var.set("🚀 제어: 활성화 중")
            self.mode_label.config(fg="green", font=("Malgun Gothic", 10, "bold"))
        else:
            self.mode_var.set("⌨️ 제어: 비활성화 (F4)")
            self.mode_label.config(fg="red", font=("Malgun Gothic", 10))

if __name__ == "__main__":
    gui = ClientGUI()
    client = WebRTCClient(gui)
    def start_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(client.run())
    threading.Thread(target=start_async,daemon=True).start()
    gui.root.mainloop()
    