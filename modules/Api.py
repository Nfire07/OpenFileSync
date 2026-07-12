"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: FastAPI server for OpenFileSync status endpoint
"""
from fastapi import FastAPI
from pathlib import Path
from pydantic import BaseModel
import uvicorn
import random
import uuid
import time


class ConnectRequest(BaseModel):
    target_ip: str
    from_ip: str


class SendOtpRequest(BaseModel):
    session_id: str
    otp: int


class CancelRequest(BaseModel):
    session_id: str


class TreeRequest(BaseModel):
    session_id: str
    path: str = None
    depth: int = 1
    hidden: bool = False


class DisconnectRequest(BaseModel):
    session_id: str


class OpenFileSyncApi:
    def __init__(self):
        """@param: none
        @return: none
        @desc: initializes FastAPI app with port and timeout settings"""
        self.app = FastAPI()
        self.APP_PORT = 8010
        self.TIMEOUT = 5
        self.sessions = {}
        self._setup_routes()

    def _setup_routes(self):
        """@param: none
        @return: none
        @desc: configures API routes for status and tree endpoints"""
        @self.app.get("/status")
        def status():
            return {"active": True, "status": "ok"}

        @self.app.post("/tree")
        def tree(req: TreeRequest):
            """@param req: TreeRequest with session_id and optional path/depth/hidden
            @return: dict representing directory tree or error
            @desc: returns directory tree after validating session"""
            session = self.sessions.get(req.session_id)
            if not session:
                return {"error": "session not found"}
            if session["status"] != "verified":
                return {"error": "session not verified"}
            base = Path(req.path) if req.path else Path.home()
            if not base.is_dir():
                return {"error": f"'{base}' is not a valid directory"}
            return self._build_tree(base, req.depth, req.hidden)

        @self.app.post("/connect")
        def connect(req: ConnectRequest):
            """@param req: ConnectRequest with target_ip and from_ip
            @return: dict with session_id and otp
            @desc: generates OTP, creates session, returns otp for target to display"""
            session_id = uuid.uuid4().hex[:12]
            otp = random.randint(1, 100)
            self.sessions[session_id] = {
                "otp": otp,
                "status": "waiting",
                "target_ip": req.target_ip,
                "from_ip": req.from_ip,
                "created_at": time.time(),
            }
            return {"session_id": session_id, "otp": otp, "target_ip": req.target_ip}

        @self.app.get("/otp-status/{session_id}")
        def otp_status(session_id: str):
            """@param session_id: unique session identifier
            @return: dict with current session status
            @desc: returns the OTP session status for target host polling"""
            session = self.sessions.get(session_id)
            if not session:
                return {"error": "session not found"}
            return {
                "session_id": session_id,
                "status": session["status"],
                "from_ip": session["from_ip"],
            }

        @self.app.post("/send-otp")
        def send_otp(req: SendOtpRequest):
            """@param req: SendOtpRequest with session_id and otp
            @return: dict with verification result
            @desc: verifies OTP from connecting host and updates session status"""
            session = self.sessions.get(req.session_id)
            if not session:
                return {"error": "session not found"}
            if session["status"] != "waiting":
                return {"error": f"session already {session['status']}"}
            if session["otp"] == req.otp:
                session["status"] = "verified"
                return {"verified": True, "session_id": req.session_id}
            return {"verified": False, "error": "invalid OTP"}

        @self.app.post("/cancel")
        def cancel(req: CancelRequest):
            """@param req: CancelRequest with session_id
            @return: dict with cancellation result
            @desc: cancels a pending OTP session"""
            session = self.sessions.get(req.session_id)
            if not session:
                return {"error": "session not found"}
            if session["status"] != "waiting":
                return {"error": f"session already {session['status']}"}
            session["status"] = "cancelled"
            return {"cancelled": True, "session_id": req.session_id}

        @self.app.get("/pending-connect")
        def pending_connect():
            """@param: none
            @return: dict with first pending session or empty dict
            @desc: returns the first session in waiting state for target polling"""
            for sid, session in self.sessions.items():
                if session["status"] == "waiting":
                    return {
                        "session_id": sid,
                        "otp": session["otp"],
                        "from_ip": session["from_ip"],
                        "target_ip": session["target_ip"],
                    }
            return {}

        @self.app.post("/disconnect")
        def disconnect(req: DisconnectRequest):
            """@param req: DisconnectRequest with session_id
            @return: dict with disconnected key
            @desc: destroys the session and notifies both sides"""
            session = self.sessions.get(req.session_id)
            if not session:
                return {"error": "session not found"}
            del self.sessions[req.session_id]
            return {"disconnected": True, "session_id": req.session_id}

    def _build_tree(self, directory: Path, depth: int, show_hidden: bool) -> dict:
        """@param directory: root Path to traverse
        @param depth: remaining depth levels to recurse
        @param show_hidden: whether to include dotfiles and dotdirs
        @return: dict representing the directory subtree
        @desc: recursively builds a nested dict of the directory tree"""
        node = {"name": directory.name, "path": str(directory), "type": "directory", "children": []}
        try:
            entries = sorted(directory.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return {"name": directory.name, "path": str(directory), "type": "directory", "error": "permission denied"}
        for entry in entries:
            if not show_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir():
                child = {"name": entry.name, "path": str(entry), "type": "directory"}
                if depth > 1:
                    child["children"] = self._build_tree(entry, depth - 1, show_hidden).get("children", [])
                else:
                    child["children"] = []
                node["children"].append(child)
            else:
                node["children"].append({"name": entry.name, "path": str(entry), "type": "file"})
        return node


    def run(self):
        """@param: none
        @return: none
        @desc: starts uvicorn server on configured port"""
        uvicorn.run(self.app, host="0.0.0.0", port=self.APP_PORT, log_level="critical")
    