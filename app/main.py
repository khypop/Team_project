from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import subprocess

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

@app.post("/connect")
async def connect():
    return {"status": "connected", "message": "AI 서버와 연결되었습니다!"}

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start-system")
async def start_system():
    # 이론: subprocess를 통해 시그널링, 서버, 클라이언트를 독립 프로세스로 가동
    subprocess.Popen(["python", "signaling.py"])
    subprocess.Popen(["python", "server_logic.py"])
    subprocess.Popen(["python", "client_logic.py"])
    return {"status": "running", "info": "AI 엔진 및 스트리밍 가동 중"}