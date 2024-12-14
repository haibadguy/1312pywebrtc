import eventlet
eventlet.monkey_patch()
from flask import Flask, request, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
import json
from aiortc import RTCPeerConnection, RTCSessionDescription

app = Flask(__name__)
CORS(app)  # Bật CORS
socketio = SocketIO(app, cors_allowed_origins="*")

pcs = {}

@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@socketio.on("connect")
def on_connect():
    print("Client connected")

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    print(f"Client disconnected: {sid}")
    if sid in pcs:
        pc = pcs.pop(sid)
        pc.close()

@socketio.on("offer")
def handle_offer(data):
    sid = request.sid
    print("Offer received from", sid)
    params = json.loads(data)

    pc = RTCPeerConnection(configuration={
        "iceServers": [{"urls": "stun:stun.l.google.com:19302"}]
    })
    pcs[sid] = pc

    @pc.on("iceconnectionstatechange")
    def on_iceconnectionstatechange():
        print(f"ICE state: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            pc.close()
            pcs.pop(sid, None)

    @pc.on("track")
    def on_track(track):
        print(f"Track received: {track.kind}")

    try:
        pc.setRemoteDescription(
            RTCSessionDescription(sdp=params["sdp"], type=params["type"])
        )
        answer = pc.createAnswer()
        pc.setLocalDescription(answer)
        socketio.emit("answer", json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }), room=sid)
    except Exception as e:
        print(f"Error handling offer: {e}")

@socketio.on("candidate")
def handle_candidate(data):
    sid = request.sid
    print(f"ICE Candidate received from {sid}: {data}")
    try:
        candidate = json.loads(data)
        pc = pcs.get(sid)
        if pc:
            pc.addIceCandidate(candidate)
            print(f"Candidate added for {sid}")
    except Exception as e:
        print(f"Error handling ICE candidate: {e}")

if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()  # Gọi monkey_patch trước khi import các thư viện khác
    socketio.run(app, host="0.0.0.0", port=5000)

