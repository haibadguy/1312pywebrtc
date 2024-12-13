import re
import asyncio
import json
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
import socketio
import os

# Tạo server Socket.IO
sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

pcs = {}  # Danh sách các kết nối peer, lưu theo ID của mỗi client

def parse_candidate(candidate_str):
    # Mẫu regex để phân tích candidate, hỗ trợ nhiều loại candidate khác nhau
    pattern = r"candidate:(\S+) (\d+) (\w+) (\d+) (\d+\.\d+\.\d+\.\d+) (\d+) typ (\w+)( raddr (\d+\.\d+\.\d+\.\d+) rport (\d+))? generation (\d+) ufrag (\S+) network-id (\d+)( network-cost (\d+))?"
    match = re.match(pattern, candidate_str)
    
    if match:
        # Trích xuất các nhóm dữ liệu từ chuỗi match
        candidate = match.group(1)
        component = int(match.group(2))
        protocol = match.group(3)
        priority = int(match.group(4))
        ip = match.group(5)
        port = int(match.group(6))
        type_ = match.group(8)
        generation = int(match.group(13))
        ufrag = match.group(14)
        network_id = int(match.group(15))
        network_cost = int(match.group(17)) if match.group(17) else None
        raddr = match.group(9)  # Địa chỉ nếu có
        rport = int(match.group(10)) if match.group(10) else None
        
        # Trả về đối tượng RTCIceCandidate
        return RTCIceCandidate(candidate, component, protocol, priority, ip, port, type_, generation, ufrag)
    else:
        print("Failed to parse candidate.")
        return None

# Sự kiện kết nối của client
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

# Sự kiện ngắt kết nối của client
@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Hủy tất cả các kết nối peer liên quan
    if sid in pcs:
        await pcs[sid].close()
        del pcs[sid]

# Xử lý offer từ client
@sio.on("offer")
async def handle_offer(sid, data):
    print("Offer received from", sid)
    params = json.loads(data)
    pc = RTCPeerConnection()
    pcs[sid] = pc

    # Thêm ICE servers cho Peer Connection
    pc = RTCPeerConnection({
        "iceServers": [
            {"urls": "stun:stun1.l.google.com:19302"},
            {"urls": "stun:stun2.l.google.com:19302"}
        ]
    })

    # Xử lý ICE candidates
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"ICE state: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            await pc.close()
            del pcs[sid]

    @pc.on("track")
    def on_track(track):
        print(f"Track received: {track.kind}")
        if track.kind == "video":
            pc.addTrack(track)  # Đơn giản chỉ thêm track vào PC để client nhận được

    # Thiết lập Remote Description
    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    )

    # Trả lời bằng answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("Sending answer to client")
    await sio.emit("answer", json.dumps({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }), room=sid)

# Xử lý candidate nhận được
@sio.on("candidate")
async def handle_candidate(sid, data):
    print("Candidate received:", data)
    
    try:
        params = json.loads(data)
        candidate_str = params.get("candidate")
        
        if candidate_str:
            candidate = parse_candidate(candidate_str)

            if candidate:
                # Tìm kiếm peer connection theo SID và thêm candidate vào peer connection
                pc = pcs.get(sid)
                if pc:
                    await pc.addIceCandidate(candidate)
                    print(f"ICE Candidate added to peer connection for SID: {sid}")
                else:
                    print(f"No peer connection found for SID: {sid}")
            else:
                print(f"Failed to parse candidate: {candidate_str}")
        else:
            print("No candidate found in the message")
    
    except json.JSONDecodeError:
        print("Invalid JSON format")

# Route để phục vụ trang index
async def index(request):
    with open("index.html", encoding="utf-8") as f:
        return web.Response(content_type="text/html", text=f.read())

# Thêm các route vào ứng dụng
app.router.add_get("/", index)

# Thiết lập Render environment
if os.getenv('RENDER_EXTERNAL_URL'):
    public_url = os.getenv('RENDER_EXTERNAL_URL')
    print(f"Public URL: {public_url}")

# Chạy server trên Render (cổng 8080 mặc định)
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
