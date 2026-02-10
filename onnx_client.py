import gi
import json
import asyncio
import websockets
import time
import numpy as np
import os
import sys

# MSYS2의 DLL 폴더와 ONNX Runtime의 DLL 폴더를 강제로 등록합니다.
if os.name == 'nt':
    # 1. MSYS2 바이너리 경로 추가
    os.add_dll_directory(r"C:\msys64\mingw64\bin")
    # 2. ONNX Runtime CAPI 경로 추가
    os.add_dll_directory(r"C:\msys64\mingw64\lib\python3.12\site-packages\onnxruntime\capi")
    # 3. 윈도우 시스템32 경로 추가 (보험)
    os.add_dll_directory(r"C:\Windows\System32")
import onnxruntime as ort
from pynput import mouse, keyboard




gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
gi.require_version('GstApp','1.0')
from gi.repository import Gst, GstWebRTC, GstSdp, GstApp

Gst.init(None)

class WebRTCClient:
    def __init__(self):

        self.ort_session = ort.InferenceSession("fsrcnn_x2.onnx", providers=['CPUExecutionProvider'])

        self.pipe_str = (
            "webrtcbin name=recv bundle-policy=max-bundle "
            "stun-server=stun://stun.l.google.com:19302 "
            "decodebin name=dbin ! videoconvert ! video/x-raw,format=BGR ! "
            "appsink name=sink emit-signals=true sync=false"
        )
        self.pipeline = Gst.parse_launch(self.pipe_str)
        # self.webrtc = self.pipeline.get_by_name("recv") #webrtc 핸들
        self.appsink = self.pipeline.get_by_name("sink")
        self.appsink.connect("new-sample",self.on_new_sample)
        
        self.out_width = 2560
        self.out_height = 1600
        self.out_pipe_str = (
            f"appsrc name=asrc format=time is-live=true do-timestamp=true ! "
            f"video/x-raw,format=BGR,width={self.out_width},height={self.out_height},framerate=0/1 ! "
            f"videoconvert ! autovideosink sync=false"
        )

        self.out_pipeline=Gst.parse_launch(self.out_pipe_str)
        self.appsrc=self.out_pipeline.get_by_name("asrc")
        self.out_pipeline.set_state(Gst.State.PLAYING)

        self.webrtc = self.pipeline.get_by_name("recv")
        
        self.data_channel = None #서버에서 연 데이터 채널 저장
        self.is_open = False #데이터 채널 오픈 여부 
        self.last_move_time= 0 

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.conn = await websockets.connect('ws://172.30.1.86:8888')
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

    def on_new_sample(self,sink):
        sample = sink.emit("pull-sample")
        buffer = sample.get_buffer()
        caps = sample.get_caps()

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success: return Gst.FlowReturn.ERROR

        h = caps.get_structure(0).get_value("height")
        w = caps.get_structure(0).get_value("width")

        frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((h, w, 3))
        buffer.unmap(map_info)

        # 2. AI 업스케일링 전처리
        input_tensor = frame.transpose(2, 0, 1).astype(np.float32) / 255.0
        input_tensor = np.expand_dims(input_tensor, axis=0)
        
        # 3. ONNX 추론
        ort_inputs = {self.ort_session.get_inputs()[0].name: input_tensor}
        ort_outs = self.ort_session.run(None, ort_inputs)
        
        # 4. 후처리 (결과를 다시 GStreamer 버퍼로 변환)
        output = np.clip(ort_outs[0].squeeze(0) * 255.0, 0, 255).astype(np.uint8)
        upscaled_data = output.transpose(1, 2, 0).tobytes()

        # 5. 출력 파이프라인(appsrc)으로 데이터 푸시
        new_buf = Gst.Buffer.new_allocate(None, len(upscaled_data), None)
        new_buf.fill(0, upscaled_data)
        self.appsrc.emit("push-buffer", new_buf)
        
        return Gst.FlowReturn.OK

    def on_data_channel(self, webrtc, channel):
        self.data_channel = channel #데이터 채널 저장 
        channel.connect("on-open", self.on_channel_open) #데이터 채널 활성화 감지
 
    def on_channel_open(self, channel):
        print("🔓 원격 제어 활성화 (모든 키/마우스 전송)")
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
                print("원격제어 종료(F12)")
                self.pipeline.set_state(Gst.State.NULL)
                self.out_pipeline.set_state(Gst.State.NULL)
                self.key_listener.stop()
                self.mouse_listener.stop()
                return False
            if key == keyboard.Key.f4:
                self.control_active = not self.control_active
                status = "활성화" if self.control_active else "비활성화"
                print(f"키보드 마우스 제어{status}")
                return
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
        
        self.mouse_listener=mouse.Listener(
            on_move=on_move, on_click=on_click,on_scroll=on_scroll,
            daemon=True)
        self.key_listener=keyboard.Listener(
            on_press=on_press,on_release=on_release,
            suppress=True, daemon=True)
        self.mouse_listener.start()
        self.key_listener.start()

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