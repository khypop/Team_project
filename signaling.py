import asyncio
import websockets
import json

peers = {}

async def handler(ws):
    pid = None
    try:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "register":
                pid = data["id"]
                peers[pid] = ws
                print(f"✅ {pid} 등록 완료")
            else:
                target = data.get("target")
                if target in peers:
                    await peers[target].send(json.dumps(data))
    except: pass
    finally:
        if pid in peers: del peers[pid]

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8888):
        print("🚀 시그널링 서버 가동 중...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())