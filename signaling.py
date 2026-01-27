import asyncio
import websockets

clients = {}

async def handler(websocket):
    role = None
    try:
        # 첫 메시지로 역할 등록 (server 또는 client)
        role = await websocket.recv()
        clients[role] = websocket
        print(f"✨ [{role}] 연결됨")

        async for message in websocket:
            # 상대방에게 메시지 전달
            target = "client" if role == "server" else "server"
            if target in clients:
                await clients[target].send(message)
    except Exception as e:
        print(f"❌ 시그널링 에러: {e}")
    finally:
        if role in clients:
            del clients[role]
            print(f"🔌 [{role}] 연결 종료")

async def main():
    print("🚀 시그널링 서버 가동 (Port: 8080)")
    async with websockets.serve(handler, "0.0.0.0", 8080):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())