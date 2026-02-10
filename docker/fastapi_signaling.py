from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json
import socket
import struct

app = FastAPI()

# HTML 템플릿 설정을 위해 (index.html이 들어갈 폴더)
templates = Jinja2Templates(directory="templates")

# 연결된 기기들을 저장할 딕셔너리 (기존 peers 역할)
peers = {}

# --- [부팅 관련 설정] ---
TARGET_MAC = "AA:BB:CC:DD:EE:FF"  # 나중에 본인 PC MAC 주소로 수정
ROUTER_IP = "192.168.0.1"        # 본인 공유기 외부 IP 혹은 DDNS

# 1. 웹사이트 메인 화면
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 2. PC 깨우기 API (버튼 누르면 실행)
@app.post("/wakeup")
async def wakeup():
    # WoL 패킷 생성 및 전송 로직
    cleaned_mac = TARGET_MAC.replace(':', '').replace('-', '')
    packet = struct.pack('!B', 0xff) * 6 + struct.pack('!BBBBBB', *[int(cleaned_mac[i:i+2], 16) for i in range(0, 12, 2)]) * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(packet, (ROUTER_IP, 9))
    return {"status": "success", "message": "부팅 신호 전송 완료!"}

# 3. 시그널링 서버 로직 (사용자님의 기존 코드를 FastAPI식으로 변환)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pid = None
    try:
        while True:
            # 메시지 수신
            msg = await websocket.receive_text()
            data = json.loads(msg)
            
            # 등록 로직
            if data.get("type") == "register":
                pid = data["id"]
                peers[pid] = websocket
                print(f"✅ {pid} 등록 완료")
            
            # 중계 로직
            else:
                target = data.get("target")
                if target in peers:
                    # 대상에게 메시지 전달
                    await peers[target].send_text(json.dumps(data))
                    
    except WebSocketDisconnect:
        if pid in peers:
            del peers[pid]
            print(f"❌ {pid} 연결 종료")
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")
        if pid in peers:
            del peers[pid]