import gi
import json
import asyncio
import websockets
from pynput.keyboard import Key, Controller as KeyboardController, KeyCode
from pynput.mouse import Button, Controller as MouseController

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)

class WebRTCServer:
    def __init__(self, sig_ip):
        self.sig_url = f"ws://{sig_ip}:8080"
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.webrtc = None

    def on_channel_message(self, chan, msg):
        p = msg.split(',')
        try:
            if p[0] == "MM": self.mouse.position = (int(p[1]), int(p[2]))
            elif p[0] == "MC":
                btn = getattr(Button, p[1].lower(), Button.left)
                if p[2] == 'D': self.mouse.press(btn)
                else: self.mouse.release(btn)
            elif p[0] in ["KD", "KU"]:
                k = KeyCode.from_vk(int(p[2])) if p[1] == 'VK' else \
                    getattr(Key, p[2].split('.')[1], None) if p[1] == 'SP' else p[2]
                if p[0] == "KD": self.keyboard.press(k)
                else: self.keyboard.release(k)
        except: pass

    def start_pipeline(self):
        pipeline_str = """
            d3d11screencapturesrc show-cursor=true ! 
            d3d11convert ! d3d11download ! videoconvert ! 
            video/x-raw,format=I420 ! 
            x264enc tune=zerolatency speed-preset=ultrafast bitrate=3000 !
            rtph264pay config-interval=1 ! 
            application/x-rtp,media=video,encoding-name=H264,payload=96 ! 
            webrtcbin name=sendrecv bundle-policy=max-bundle
        """
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.webrtc = self.pipeline.get_by_name("sendrecv")
        self.webrtc.connect("on-ice-candidate", self.send_ice)
        self.webrtc.connect("on-data-channel", lambda _, c: c.connect("on-message-string", self.on_channel_message))
        
        # 서버는 보내는 역할(SENDONLY)임을 명시
        direction = GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY
        self.webrtc.emit("add-transceiver", direction, None)

        self.pipeline.set_state(Gst.State.PLAYING)
        print("[STEP 2] 서버 파이프라인 가동 (Offer 수신 대기 중...)")

    def send_ice(self, _, idx, cand):
        msg = json.dumps({"ice": {"candidate": cand, "sdpMLineIndex": idx}})
        asyncio.run_coroutine_threadsafe(self.ws.send(msg), self.loop)

    async def run(self):
        self.loop = asyncio.get_event_loop()
        async with websockets.connect(self.sig_url) as ws:
            self.ws = ws
            await ws.send("server")
            print("[STEP 1] 서버 등록 완료")
            self.start_pipeline()
            async for message in ws:
                try: msg = json.loads(message)
                except: continue
                if "sdp" in msg:
                    print("📩 Offer 수신! Answer 생성 중...")
                    res, sdp = GstSdp.SDPMessage.new()
                    GstSdp.sdp_message_parse_buffer(bytes(msg["sdp"]["sdp"], 'utf-8'), sdp)
                    desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdp)
                    self.webrtc.emit("set-remote-description", desc, None)
                    promise = Gst.Promise.new()
                    self.webrtc.emit("create-answer", None, promise)
                    promise.wait()
                    ans = promise.get_reply().get_value("answer")
                    self.webrtc.emit("set-local-description", ans, None)
                    await self.ws.send(json.dumps({"sdp": {"type": "answer", "sdp": ans.sdp.as_text()}}))
                    print("📤 Answer 전송 완료!")
                elif "ice" in msg:
                    self.webrtc.emit("add-ice-candidate", msg["ice"]["sdpMLineIndex"], msg["ice"]["candidate"])

if __name__ == "__main__":
    asyncio.run(WebRTCServer("172.30.1.98").run())