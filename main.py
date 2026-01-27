import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import socket
import threading

Gst.init(None)

def start_gst_pipeline(target_ip):
    # 송신 파이프라인: 윈도우 화면 캡처 -> H.264 인코딩 -> UDP 전송
    pipeline_str = (
        f"dxgiscreencapsrc ! videoconvert ! "
        f"video/x-raw,framerate=30/1,format=I420 ! "
        f"x264enc tune=zerolatency speed-preset=ultrafast bframes=0 bitrate=4000 key-int-max=5 ! "
        f"rtph264pay mtu=400 config-interval=1 ! "
        f"udpsink host={target_ip} port=5000 sync=false async=false"
    )
    
    pipeline = Gst.parse_launch(pipeline_str)
    pipeline.set_state(Gst.State.PLAYING)
    print(f"--- [화면 송출 시작] 목적지: {target_ip} ---")
    
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.set_state(Gst.State.NULL)

def handle_client(conn, addr):
    print(f"클라이언트 연결됨: {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            # 2단계에서 여기에 마우스/키보드 제어 로직(pyautogui)이 들어갑니다.
            print(f"수신된 제어 신호: {data.decode()}")
    except Exception as e:
        print(f"연결 오류: {e}")
    finally:
        conn.close()

def run_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('0.0.0.0', 9999))
    server_sock.listen(5)
    print("서버 대기 중 (포트 9999)...")

    while True:
        conn, addr = server_sock.accept()
        # GStreamer 송출 시작 (연결된 클라이언트 IP로)
        gst_thread = threading.Thread(target=start_gst_pipeline, args=(addr[0],))
        gst_thread.start()
        
        # 제어 신호 수신 시작
        client_thread = threading.Thread(target=handle_client, args=(conn, addr))
        client_thread.start()

if __name__ == "__main__":
    run_server()