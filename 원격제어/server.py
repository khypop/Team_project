

import json
import asyncio
import websockets
import pyautogui
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)
pyautogui.PAUSE = 0

class WebRTCServer:
    def __init__(self):
        self.conn = None
        self.pipeline = None
        self.webrtc = None
        self.data_channel = None
        # 본인의 시그널링 서버 주소로 수정하세요
        self.ws_url = 'wss://contributed-status-bridges-occasional.trycloudflare.com/ws'

    def setup_pipeline(self):
        
        if self.pipeline:
            print("♻️ 기존 파이프라인 제거 중...")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.webrtc = None
            self.data_channel = None

        
        pipe_str = (
            "webrtcbin name=sendrecv bundle-policy=max-bundle "
            "stun-server=stun://stun.l.google.com:19302 "
            "d3d11screencapturesrc show-cursor=true ! videoconvert ! video/x-raw,format=I420 ! "
            "x264enc tune=zerolatency bitrate=2500 speed-preset=ultrafast key-int-max=15 ! "
            "rtph264pay config-interval=1 pt=96 ! sendrecv."
        )
        
        try:
            self.pipeline = Gst.parse_launch(pipe_str)
            self.webrtc = self.pipeline.get_by_name('sendrecv')
            
            if not self.webrtc:
                raise Exception("❌ 파이프라인에서 'sendrecv'(webrtcbin)를 찾을 수 없습니다.")

            # 시그널 연결
            self.webrtc.connect('on-ice-candidate', self.on_ice_candidate)
            self.webrtc.connect('on-negotiation-needed', self.on_negotiation_needed)
            
            # 파이프라인 시작
            self.pipeline.set_state(Gst.State.PLAYING)
            print("🛠️ 파이프라인 재생성 및 가동 완료")
            return True
        except Exception as e:
            print(f"❌ 파이프라인 설정 실패: {e}")
            return False

    async def run(self):
        while True:
            try:
                self.loop = asyncio.get_running_loop()
                print(f"📡 시그널링 서버 접속 시도: {self.ws_url}")
                async with websockets.connect(self.ws_url) as websocket:
                    self.conn = websocket
                    # 최초 접속 시 한 번 초기화
                    self.setup_pipeline()
                    await self.conn.send(json.dumps({'type': 'register', 'id': 'server'}))
                    print("🚀 시그널링 서버 등록 완료")
                    
                    async for message in self.conn:
                        msg = json.loads(message)
                        if msg['type'] == 'answer':
                            await self.handle_answer(msg['sdp'])
                        elif msg['type'] == 'candidate':
                            if self.webrtc:
                                self.webrtc.emit('add-ice-candidate', msg['sdpMLineIndex'], msg['candidate'])
                        elif msg.get('type') == 'new_peer' and msg.get('id') == 'client':
                            print("📱 클라이언트 감지! 파이프라인 초기화 및 협상 시작...")
                            if self.setup_pipeline():
                                self.on_negotiation_needed(self.webrtc)
            except Exception as e:
                print(f"🔄 연결 오류({e}), 5초 후 재시도...")
                await asyncio.sleep(5)

    def on_negotiation_needed(self, element):
        if not self.data_channel: #데이터 채널 생성 
            print("🛠️ 설계도에 데이터 채널 추가...")
            # 명시적으로 ordered 속성을 주어 생성
            options = Gst.Structure.new_empty("datachannel-properties")
            options.set_value("ordered", True) #데이터 채널 순서 보장 
            #control 이름의 데이터 채널 생성 
            self.data_channel = self.webrtc.emit('create-data-channel', 'control', options)
            #문자열 메시지 수신 처리
            self.data_channel.connect('on-message-string', self.on_message)
            self.data_channel.connect('on-open', lambda _: print("🔓 [성공] 서버 데이터 채널 오픈!"))
        #offer 생성 
        promise = Gst.Promise.new_with_change_func(self.on_offer_created)
        element.emit('create-offer', None, promise)

    def on_message(self, channel, data):
        try:
            msg = json.loads(data)
            m_type = msg.get('type')

            if m_type == 'mousemove':
                pyautogui.moveTo(msg['x'], msg['y'])
            elif m_type == 'mousedown':
                pyautogui.mouseDown(x=msg['x'], y=msg['y'], button=msg.get('button', 'left'))
            elif m_type == 'mouseup':
                pyautogui.mouseUp(x=msg['x'], y=msg['y'],button=msg.get('button', 'left'))
            elif m_type == 'mousescroll':
                dy=msg.get('dy',0)

                if dy > 0:
                    pyautogui.scroll(int(dy * 160))
                else:
                    pyautogui.scroll(int(dy * 120))
                    
            elif m_type in ['keydown','keyup']:
                key = msg.get('key')
                # 특수키 매핑 (필요 시 추가)
                special_key_map = {
                'ctrl_l': 'ctrl',
                'ctrl_r': 'ctrl',
                'shift_l': 'shift',
                'shift_r': 'shift',
                'alt_l': 'alt',
                'alt_r': 'alt',
                'alt_gr': 'alt',
                'cmd': 'win',      
                'cmd_r': 'win',
                'enter': 'enter',
                'backspace': 'backspace',
                'tab': 'tab',
                'esc': 'esc',
                'space': 'space',
                'caps_lock': 'capslock',
                'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
                'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
                'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
                'home': 'home',
                'end': 'end',
                'page_up': 'pgup',
                'page_down': 'pgdn',
                'left': 'left',
                'right': 'right',
                'up': 'up',
                'down': 'down',
                'delete': 'delete',
                'insert': 'insert',
                'hangul': 'hangul',
                'hanja': 'hanja'
            }
                target_key=special_key_map.get(key, key)
                if m_type == 'keydown':
                    pyautogui.keyDown(target_key)
                else:
                    pyautogui.keyUp(target_key)

        except Exception as e:
            print(f"❌ 제어 실행 오류: {e}")

    def on_offer_created(self, promise):
        reply = promise.get_reply()
        offer = reply.get_value('offer')
        self.webrtc.emit('set-local-description', offer, None)
        msg = {'type': 'offer', 'target': 'client', 'sdp': offer.sdp.as_text()}
        asyncio.run_coroutine_threadsafe(self.conn.send(json.dumps(msg)), self.loop)

    async def handle_answer(self, sdp_text):
        res, sdp = GstSdp.SDPMessage.new()
        GstSdp.SDPMessage.parse_buffer(sdp_text.encode(), sdp)
        answer = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, sdp)
        self.webrtc.emit('set-remote-description', answer, None)

    def on_ice_candidate(self, element, mline, candidate):
        msg = {'type': 'candidate', 'target': 'client', 'sdpMLineIndex': mline, 'candidate': candidate}
        asyncio.run_coroutine_threadsafe(self.conn.send(json.dumps(msg)), self.loop)

if __name__ == "__main__":
    asyncio.run(WebRTCServer().run())