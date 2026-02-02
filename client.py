import gi
import json
import asyncio
import websockets
import time
from pynput import mouse, keyboard

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)

class WebRTCClient:
    def __init__(self):
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
    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.conn = await websockets.connect("wss://voice-raw-regulatory-area.trycloudflare.com")
        await self.conn.send(json.dumps({"type": "register", "id": "client"}))
        #ice 후보 생성 시 호출 및 데이터 채널 수신  
        self.webrtc.connect("on-ice-candidate", self.on_ice_candidate)
        self.webrtc.connect("pad-added", self.on_pad_added)
        self.webrtc.connect("on-data-channel", self.on_data_channel)

        self.pipeline.set_state(Gst.State.PLAYING)
        print("🚀 [클라이언트] 서버 연결 대기 중...")

        async for message in self.conn:
            msg = json.loads(message)
            if msg["type"] == "offer": #SDP offer 수신 
                await self.handle_offer(msg["sdp"])
            elif msg["type"] == "candidate": #ice 후보 추가 
                self.webrtc.emit("add-ice-candidate", msg["sdpMLineIndex"], msg["candidate"])

    def on_data_channel(self, webrtc, channel):
        self.data_channel = channel #데이터 채널 저장 
        channel.connect("on-open", self.on_channel_open) #데이터 채널 활성화 감지
 
    def on_channel_open(self, channel):
        print("🔓 원격 제어 활성화 (모든 키/마우스 전송)")
        self.is_open = True  # 데이터 채널 오픈 키보드/마우스 제어 가능 
        self.start_listeners()

    def start_listeners(self):
        # 마우스 이동 및 클릭
        def on_move(x, y):
            cur=time.time() 
            if self.is_open and (cur-self.last_move_time > 0.05):
                self.send_ctrl({"type": "mousemove", "x": int(x), "y": int(y)})
                self.last_move_time= cur
        def on_click(x, y, button, pressed):
            if self.is_open:
                btn = 'left' if button == mouse.Button.left else 'right'
                action="mousedown" if pressed else "mouseup"
                self.send_ctrl({"type": action, "x":int(x), "y":int(y),"button":btn})
        
        def on_scroll(x,y,dx,dy):
            if self.is_open:
                self.send_ctrl({"type":"mousescroll","dx":dx,"dy":dy})

        # 키보드 입력
        def on_press(key):
            if self.is_open:
                try:
                    if hasattr(key,'char') and key.char:
                        k=key.char
                    elif hasattr(key,'vk'):
                        if key.vk==21: k='hangul'
                        elif key.vk==25: k='hanja'
                        else: k= key.name
                    else:
                        k= key.name
                    self.send_ctrl({"type": "keypress", "key":k})
                except: pass

        mouse.Listener(on_move=on_move, on_click=on_click,on_scroll=on_scroll, daemon=True).start()
        keyboard.Listener(on_press=on_press, daemon=True).start()

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

if __name__ == "__main__":
    asyncio.run(WebRTCClient().run())