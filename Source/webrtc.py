import asyncio
import socketio
import gi
import sys

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GLib

# ★ 라즈베리파이 VPN IP 확인
SIGNALING_URL = 'http://10.6.0.1:8000'

Gst.init(None)

class WebRTCHost:
    def __init__(self):
        self.sio = socketio.AsyncClient()
        self.webrtc = None
        self.pipe = None
        
    def build_pipeline(self):
        # 윈도우 화면 캡처 -> H.264 압축 -> 전송
        #pipeline_str = '''
        #    webrtcbin name=sendrecv bundle-policy=max-bundle
        #    dxgiscreencapsrc ! videoconvert ! video/x-raw,format=I420 ! 
        #    x264enc tune=zerolatency bitrate=4000 speed-preset=ultrafast key-int-max=30 ! 
        #    rtph264pay config-interval=-1 ! 
        #    application/x-rtp,media=video,encoding-name=H264,payload=96 ! 
        #    sendrecv.
        #'''

        pipeline_str = '''
            webrtcbin name=sendrecv bundle-policy=max-bundle
            d3d11screencapturesrc show-cursor=true ! 
            d3d11convert ! 
            d3d11download ! 
            videoconvert ! video/x-raw,format=NV12 ! 
            nvh264enc preset=low-latency-hq zerolatency=true bitrate=3000 rc-mode=cbr ! 
            rtph264pay config-interval=-1 ! 
            application/x-rtp,media=video,encoding-name=H264,payload=96 ! 
            sendrecv.
        '''
        
        try:
            self.pipe = Gst.parse_launch(pipeline_str)
            self.webrtc = self.pipe.get_by_name('sendrecv')
            
            # 시그널링(연결) 이벤트 연결
            self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
            self.webrtc.connect('on-ice-candidate', self.on_ice_candidate)
            
            self.pipe.set_state(Gst.State.PLAYING)
            print("🎥 화면 캡처 시작 (대기 중...)")
        except Exception as e:
            print(f"❌ 파이프라인 에러: {e}")

    async def start(self):
        @self.sio.event
        async def connect():
            print("✅ 시그널링 서버 접속됨! (연결 준비 완료)")
            self.build_pipeline()

        @self.sio.event
        async def message(data):
            # 상대방(노트북)의 응답(Answer) 처리
            if 'sdp' in data and data['sdp']['type'] == 'answer':
                print("📩 Answer 수신 (연결 수립 중...)")
                res, sdpmsg = GstSdp.sdp_message_new_from_text(data['sdp']['sdp'])
                desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSdpType.ANSWER, sdpmsg)
                promise = Gst.Promise.new()
                self.webrtc.emit('set-remote-description', desc, promise)
                promise.interrupt()
            
            # 상대방의 네트워크 경로(Candidate) 처리
            elif 'candidate' in data and self.webrtc:
                self.webrtc.emit('add-ice-candidate', data['candidate']['sdpMLineIndex'], data['candidate']['candidate'])

        await self.sio.connect(SIGNALING_URL)
        await self.sio.wait()

    def on_negotiation_needed(self, element):
        # 내가 먼저 연결 요청(Offer) 생성
        promise = Gst.Promise.new_with_change_func(self.on_offer_created, element, None)
        element.emit('create-offer', None, promise)

    def on_offer_created(self, promise, _, __):
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        
        promise = Gst.Promise.new()
        self.webrtc.emit('set-local-description', offer, promise)
        promise.interrupt()
        
        # 서버로 전송
        text = GstSdp.sdp_message_as_text(offer)
        msg = {'sdp': {'type': 'offer', 'sdp': text}}
        asyncio.run_coroutine_threadsafe(self.sio.emit('message', msg), self.loop)

    def on_ice_candidate(self, _, mlineindex, candidate):
        msg = {'candidate': {'candidate': candidate, 'sdpMLineIndex': mlineindex}}
        asyncio.run_coroutine_threadsafe(self.sio.emit('message', msg), self.loop)

if __name__ == "__main__":
    host = WebRTCHost()
    loop = asyncio.new_event_loop()
    host.loop = loop
    
    # GStreamer용 별도 스레드
    import threading
    threading.Thread(target=lambda: GLib.MainLoop().run(), daemon=True).start()
    
    try:
        loop.run_until_complete(host.start())
    except KeyboardInterrupt:
        print("종료합니다.")