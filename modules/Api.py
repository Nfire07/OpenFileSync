"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: FastAPI server for OpenFileSync status endpoint
"""
from fastapi import FastAPI
import uvicorn

class OpenFileSyncApi:
    def __init__(self):
        """@param: none
        @return: none
        @desc: initializes FastAPI app with port and timeout settings"""
        self.app = FastAPI()
        self.APP_PORT = 8010
        self.TIMEOUT = 1.5
        self._setup_routes()

    def _setup_routes(self):
        """@param: none
        @return: none
        @desc: configures API routes for status endpoint"""
        @self.app.get("/status")
        def status():
            return {"active": True, "status": "ok"}

    def run(self):
        """@param: none
        @return: none
        @desc: starts uvicorn server on configured port"""
        uvicorn.run(self.app, host="0.0.0.0", port=self.APP_PORT)