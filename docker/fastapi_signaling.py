from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import json
import socket
import struct
import time
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML 템플릿 설정을 위해 (index.html이 들어갈 폴더)
templates = Jinja2Templates(directory="templates")

#-----데이터 베이스 설정---------
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://smj:kit2025!@db/remote_db")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,)
SessionLocal = sessionmaker(autocommit=False,autoflush=False,bind=engine)
Base = declarative_base()

#------유저 테이블 정의------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password = Column(String(100))

# [중요] 앱이 시작될 때 DB 접속을 시도하고, 안되면 기다립니다.
@app.on_event("startup")
def startup_event():
    for _ in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ DB 연결 성공!")
            return
        except Exception as e:
            print(f"⚠️ DB 대기 중... 1초 뒤 재시도: {e}")
            time.sleep(1)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# 연결된 기기들을 저장할 딕셔너리 (기존 peers 역할)
peers = {}

# --- [부팅 관련 설정] ---
TARGET_MAC = "AA:BB:CC:DD:EE:FF"  # 나중에 본인 PC MAC 주소로 수정
ROUTER_IP = "192.168.0.1"        # 본인 공유기 외부 IP 혹은 DDNS

#----[페이지 이동]--------
# 1. 웹사이트 메인 화면
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    # 쿠키에서 'session_user'를 가져와 index.html에 전달
    user = request.cookies.get("session_user")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


# 2. PC 깨우기 API
@app.post("/wakeup")
async def wakeup(request: Request):
    # 보안: 로그인한 사용자만 깨우기 가능
    if not request.cookies.get("session_user"):
        return {"status": "error", "message": "로그인이 필요합니다."}

    cleaned_mac = TARGET_MAC.replace(':', '').replace('-', '')
    packet = struct.pack('!B', 0xff) * 6 + struct.pack('!BBBBBB', *[int(cleaned_mac[i:i+2], 16) for i in range(0, 12, 2)]) * 16
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(packet, (ROUTER_IP, 9))
    return {"status": "success", "message": "부팅 신호 전송 완료!"} 

# -----[로그인 회원가입 데이터 처리(DB 저장)] ------
@app.post("/register")
async def do_register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # 이미 존재하는 아이디인지 확인
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return HTMLResponse(content="이미 존재하는 아이디입니다.", status_code=400)
    
    # DB에 새 유저 저장
    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()
    print(f"✅ DB 저장 완료: {username}")
    return RedirectResponse(url="/login", status_code=303)

# --- [4. 실제 로그인 로직 (DB 대조)] ---
@app.post("/login")
async def do_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # DB에서 아이디와 비번이 맞는지 확인
    user = db.query(User).filter(User.username == username, User.password == password).first()
    
    if user:
        print(f"✅ 로그인 성공: {username}")
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_user", value=username)
        return response
    else:
        return HTMLResponse(content="아이디 또는 비밀번호가 틀렸습니다.", status_code=401)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_user")
    return response

#-----웹소켓------------------
# 3. 시그널링 서버 로직 (사용자님의 기존 코드를 FastAPI식으로 변환)
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    pid = None
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            
            if data.get("type") == "register":
                pid = data["id"]
                peers[pid] = websocket
                print(f"✅ {pid} 등록 완료 (현재 접속자: {list(peers.keys())})")

                # 상대방 ID 결정
                other_id = "client" if pid == "server" else "server"
                
                # 만약 상대방이 이미 접속해 있다면 양쪽에 알림
                if other_id in peers:
                    print(f"🔗 {pid} <-> {other_id} 매칭 시도")
                    # 신규 접속자에게 기존에 있던 피어 알림
                    await websocket.send_text(json.dumps({"type": "new_peer", "id": other_id}))
                    # 기존 피어에게 신규 접속자 알림
                    await peers[other_id].send_text(json.dumps({"type": "new_peer", "id": pid}))
            
            else:
                target = data.get("target")
                if target in peers:
                    await peers[target].send_text(json.dumps(data))
                else:
                    print(f"❌ 배달 실패: 대상 '{target}' 없음")
                    
    except WebSocketDisconnect:
        if pid in peers:
            del peers[pid]
            print(f"❌ {pid} 연결 종료")
    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")
        if pid in peers:
            del peers[pid]