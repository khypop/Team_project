import gi
import asyncio
import websockets
import json
import time
import socket
import struct

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstWebRTC

import numpy as np
import cv2
import torch
from fsrcnn import FSRCNN

Gst.init(None)


class WebRTCClient:
    def __init__(self):
        # ------------------------------
        # FSRCNN 모델 (1번만 로드)
        # ------------------------------
        self.sock = sock.socket(sockt.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(("127.0.0.1", 5000))
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = FSRCNN(scale=2).to(self.device)
        self.model.load_state_dict(
            torch.load("fsrcnn.pth", map_location=self.device)
        )
        self.model.eval()
        print("[OK] FSRCNN model loaded")

        # ------------------------------
        # GStreamer 파이프라인
        # ------------------------------
        self.pipeline = Gst.parse_launch(
            """
            webrtcbin name=webrtcbin
            webrtcbin. ! queue ! decodebin ! videoconvert !
            video/x-raw,format=BGR !
            appsink name=appsink emit-signals=true sync=false
            """
        )

        self.webrtc = self.pipeline.get_by_name("webrtcbin")
        self.appsink = self.pipeline.get_by_name("appsink")
        self.appsink.connect("new-sample", self.on_new_sample)

    # ------------------------------
    # 프레임 처리 (핵심)
    # ------------------------------
    def on_new_sample(self, sink):
        sample = sink.emit("pull-sample")
        buffer = sample.get_buffer()

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return Gst.FlowReturn.ERROR

        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = structure.get_value("width")
        height = structure.get_value("height")

        frame = np.frombuffer(
            map_info.data, dtype=np.uint8
        ).reshape((height, width, 3))

        buffer.unmap(map_info)

        # ------------------------------
        # FSRCNN 처리
        # ------------------------------
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        data = gray.tobytes()
        self.sock.sendall(struct.pack("Q", len(data)) + data)

        # 결과 받기
        header = self.sock.recv(8)
        (size,) = struct.unpack("Q", header)

        out = b""
        while len(out) < size:
            out += self.sock.recv(size - len(out))

        sr = np.frombuffer(out, dtype=np.uint8).reshape(
            gray.shape[0]*2,
            gray.shape[1]*2
        )

        cv2.imshow("FSRCNN Output", sr)
        cv2.waitKey(1)

        return Gst.FlowReturn.OK

    # ------------------------------
    # WebSocket signaling
    # ------------------------------
    async def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)

        async with websockets.connect('wss://worker-collectors-incomplete-vocation.trycloudflare.com') as ws:
            print("[OK] signaling connected")

            async for msg in ws:
                data = json.loads(msg)

                if "sdp" in data:
                    sdp = GstWebRTC.WebRTCSessionDescription.new(
                        GstWebRTC.WebRTCSDPType.ANSWER,
                        Gst.SDPMessage.new_from_text(data["sdp"])[1]
                    )
                    self.webrtc.emit("set-remote-description", sdp)

                elif "ice" in data:
                    self.webrtc.emit(
                        "add-ice-candidate",
                        data["ice"]["sdpMLineIndex"],
                        data["ice"]["candidate"],
                    )


if __name__ == "__main__":
    client = WebRTCClient()
    asyncio.run(client.run())
