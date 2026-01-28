# signaling.py (라즈베리파이)
import socketio
from aiohttp import web
import os

# HTML 파일이 있는 경로 (현재 폴더)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sio = socketio.AsyncServer(cors_allowed_origins='*')
app = web.Application()
sio.attach(app)

ROOM_ID = "remote_control_room"

# 1. 웹페이지 요청이 오면 index.html 보내기
async def index(request):
    try:
        with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="index.html 파일을 찾을 수 없습니다.", status=404)

# 라우팅 설정
app.router.add_get('/', index)
app.router.add_static('/static', path=os.path.join(BASE_DIR, 'static'), name='static') if os.path.exists(os.path.join(BASE_DIR, 'static')) else None

@sio.event
async def connect(sid, environ):
    print(f"✅ 접속: {sid}")
    await sio.enter_room(sid, ROOM_ID)
    # 누군가 들어오면 기존에 있던 기기들에게 "새 친구 왔어(ready)"라고 알림
    await sio.emit('message', {'type': 'ready'}, room=ROOM_ID, skip_sid=sid)

@sio.event
async def message(sid, data):
    # 메시지 중계 (나 빼고 다 전송)
    await sio.emit('message', data, room=ROOM_ID, skip_sid=sid)

@sio.event
async def disconnect(sid):
    print(f"❌ 연결 끊김: {sid}")

if __name__ == '__main__':
    web.run_app(app, port=8000)