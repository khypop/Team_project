import gi
import json
import asyncio
import websockets
import time
from pynput import keyboard, mouse

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib

Gst.init(None)

class WebRTCClient:
    def __init__(self, sig_ip):
        self.sig_url = f"ws://{sig_ip}:8080"
        self.active = False
        self.last_move_time = 0
        self.datachannel = None

    def send_ctrl(self, msg):
        if self.datachannel and self.datachannel.get_property("state") == 1 and self.active:
            self.datachannel.emit("send-string", msg)

    def on_move(self, x, y):
        if time.time() - self.last_move_time > 0.03:
            self.send_ctrl(f"MM,{int(x)},{int(y)}")
            self.last_move_time = time.time()

    def on_click(self, x, y, btn, prs):
        self.send_ctrl(f"MC,{str(btn).split('.')[-1]},{'D' if prs else 'U'},{int(x)},{int(y)}")

    def on_key(self, key, state):
        if key == keyboard.Key.f4 and state == 'KD':
            self.active = not self.active
            print(f"\n🎮 제어 모드: {'ON' if self.active else 'OFF'}")
        else:
            k_type = "VK" if hasattr(key, 'vk') else "CH" if hasattr(key, 'char') else "SP"
            val = key.vk if k_type == "VK" else key.char if k_type == "CH" else str(key)
            self.send_ctrl(f"{state},{k_type},{val}")

    def start_pipeline(self):
        pipeline_str = """
            webrtcbin name=sendrecv bundle-policy=max-bundle
            rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink
        """
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.webrtc = self.pipeline.get_by_name("sendrecv")
        self.webrtc.connect("on-ice-candidate", self.send_ice)
        self.webrtc.connect("on-negotiation-needed", self.on_negotiation)
        
        # 🛑 클라이언트는 받는 역할(RECVONLY)임을 명시하여 협상 유도
        direction = GstWebRTC.WebRTCRTPTransceiverDirection.RECVONLY
        self.webrtc.emit("add-transceiver", direction, None)

        self.pipeline.set_state(Gst.State.PLAYING)
        print("[STEP 2] 클라이언트 파이프라인 가동 완료")

    def on_negotiation(self, webrtc):
        print("[STEP 3] 협상 필요 시그널 발생! Offer 생성 시작")
        if self.datachannel is None:
            self.datachannel = self.webrtc.emit("create-data-channel", "control", None)
        
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, None)
        webrtc.emit("create-offer", None, promise)

    def on_offer_created(self, promise, _):
        reply = promise.get_reply()
        offer = reply.get_value("offer")
        self.webrtc.emit("set-local-description", offer, None)
        msg = json.dumps({"sdp": {"type": "offer", "sdp": offer.sdp.as_text()}})
        asyncio.run_coroutine_threadsafe(self.ws.send(msg), self.loop)
        print("[STEP 4] Offer 전송 완료!")

    def send_ice(self, _, idx, cand):
        msg = json.dumps({"ice": {"candidate": cand, "sdpMLineIndex": idx}})
        asyncio.run_coroutine_threadsafe(self.ws.send(msg), self.loop)

    async def run(self):
        self.loop = asyncio.get_event_loop()
        async with websockets.connect(self.sig_url) as ws:
            self.ws = ws
            await ws.send("client")
            print("[STEP 1] 클라이언트 등록 완료")
            self.start_pipeline()
            
            keyboard.Listener(on_press=lambda k: self.on_key(k, 'KD'), on_release=lambda k: self.on_key(k, 'KU')).start()
            mouse.Listener(on_move=self.on_move, on_click=self.on_click).start()

            async for message in ws:
                try: msg = json.loads(message)
                except: continue
                if "sdp" in msg:
                    print("📩 Answer 수신! 연결 수립 중...")
                    res, sdp = GstSdp.SDPMessage.new()
                    GstSdp.sdp_message_parse_buffer(bytes(msg["sdp"]["sdp"], 'utf-8'), sdp)
                    desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdp)
                    self.webrtc.emit("set-remote-description", desc, None)
                elif "ice" in msg:
                    self.webrtc.emit("add-ice-candidate", msg["ice"]["sdpMLineIndex"], msg["ice"]["candidate"])

if __name__ == "__main__":
    asyncio.run(WebRTCClient("127.0.0.1").run())