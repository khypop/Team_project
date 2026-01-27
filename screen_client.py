import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import socket
import threading
import cv2
import numpy as np
import sys

Gst.init(None)

def start_receiver():
    # 수신 파이프라인: UDP 수신 -> 디코딩 -> BGR 변환 -> appsink
    pipeline_str = (
        "udpsrc port=5000 caps=\"application/x-rtp, payload=96\" ! "
        "rtpjitterbuffer latency=0 ! rtph264depay ! h264parse ! "
        "avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! "
        "appsink name=sink emit-signals=True sync=false"
    )
    
    pipeline = Gst.parse_launch(pipeline_str)
    sink = pipeline.get_by_name("sink")
    
    def on_new_sample(sink):
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.ERROR
            
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        
        # 프레임 크기 정보 추출
        s = caps.get_structure(0)
        width = s.get_value("width")
        height = s.get_value("height")
        
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if success:
            # GStreamer 버퍼를 numpy 배열로 변환
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
            
            # --- [이 자리가 AI 로직/객체탐지 넣는 곳] ---
            # 간단한 텍스트 표시 예시
            cv2.putText(frame, "AI & Remote Control Mode", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # OpenCV 창 출력
            cv2.imshow("Remote Desktop (OpenCV)", frame)
            
            # 'q' 키 누르면 종료
            if cv2.waitKey(1) & 0xFF == ord('q'):
                GLib.MainLoop().quit()
                
            buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    sink.connect("new-sample", on_new_sample)
    pipeline.set_state(Gst.State.PLAYING)
    print("[GStreamer] OpenCV를 통한 영상 수신 중...")
    
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)
        cv2.destroyAllWindows()

def run_client():
    SERVER_IP = "172.30.1.52"  # 본인의 윈도우 IP로 수정하세요
    SERVER_PORT = 9999
    
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client_sock.connect((SERVER_IP, SERVER_PORT))
        print(f"서버({SERVER_IP}) 연결 성공!")
        
        # 수신 전용 스레드 시작
        gst_thread = threading.Thread(target=start_receiver)
        gst_thread.daemon = True
        gst_thread.start()
        
        # 메인 스레드에서는 서버로 간단한 연결 유지 메시지나 제어 신호 전송 가능
        while True:
            msg = input("서버로 보낼 메시지 (종료: q): ")
            if msg == 'q':
                break
            client_sock.send(msg.encode())
            
    except Exception as e:
        print(f"연결 오류: {e}")
    finally:
        client_sock.close()

if __name__ == "__main__":
    run_client()