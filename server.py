import asyncio
import json
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
import socketio
import os

# Create Socket.IO server
sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

pcs = {}  # Dictionary to store peer connections by client ID

# Client connection event
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

# Client disconnection event
@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    if sid in pcs:
        await pcs[sid].close()
        del pcs[sid]

# Handle SDP offer from client
@sio.on("offer")
async def handle_offer(sid, data):
    print("Offer received from", sid)
    params = json.loads(data)
    pc = RTCPeerConnection()
    pcs[sid] = pc

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"ICE state: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            await pc.close()
            del pcs[sid]

    @pc.on("track")
    def on_track(track):
        print(f"Track received: {track.kind}")
        pc.addTrack(track)

    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("Sending answer to client")
    await sio.emit("answer", json.dumps({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }), room=sid)

async def index(request):
    with open("index.html", encoding="utf-8") as f:
        return web.Response(content_type="text/html", text=f.read())

app.router.add_get("/", index)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, port=port)
