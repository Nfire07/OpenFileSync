"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: Network layer for host discovery and API connectivity checks
"""
import json
import ipaddress
from scapy.all import conf, get_if_addr
import requests
from modules.KnownHosts import KnownHosts
from modules.Discovery import Discovery
from modules.Logger import setup_logger, log_exception, log_expected_error

logger = setup_logger()

class Network:
    def __init__(self):
        """@param: none
        @return: none
        @desc: initializes Network with KnownHosts and Discovery instances"""
        self.hosts = KnownHosts()
        self.discovery = Discovery()
        self.app_port = 8010
        self.timeout = 1.5

    def getAvailableHosts(self):
        """@param: none
        @return: list of discovered host dictionaries
        @desc: scans network and returns available hosts"""
        return self.discovery.scan()

    def getKnownHosts(self):
        """@param: none
        @return: list of known host dictionaries
        @desc: retrieves previously known hosts from storage"""
        return self.hosts.getHosts()

    def getHostInformation(self, host_ip: str):
        """@param host_ip: IP address of the host to check
        @return: dictionary with status key
        @desc: checks API status of a host and returns status"""
        url = f"http://{host_ip}:{self.app_port}/status"

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("active") is True and data.get("status") == "ok":
                return {"status": "active"}

            if data.get("active") is True and data.get("status") == "loading":
                return {"status": "loading"}

            return {"status": "inactive"}

        except requests.RequestException:
            return {
                "status": "inactive",
            }

    def connect(self, target_ip: str, from_ip: str):
        """@param target_ip: IP address of the target host
        @param from_ip: IP address of the local host
        @return: dict with session_id and otp, or empty dict on failure
        @desc: initiates connection to remote host and returns session data"""
        url = f"http://{target_ip}:{self.app_port}/connect"
        try:
            resp = requests.post(url, json={"target_ip": target_ip, "from_ip": from_ip}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {}

    def sendOtp(self, host_ip: str, session_id: str, otp: int):
        """@param host_ip: IP address of the host to verify OTP against
        @param session_id: unique session identifier
        @param otp: the OTP code to verify
        @return: dict with verified key and optional error
        @desc: sends OTP to remote host for verification"""
        url = f"http://{host_ip}:{self.app_port}/send-otp"
        try:
            resp = requests.post(url, json={"session_id": session_id, "otp": otp}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"verified": False, "error": "connection error"}

    def cancelSession(self, host_ip: str, session_id: str):
        """@param host_ip: IP address of the host owning the session
        @param session_id: unique session identifier
        @return: dict with cancelled key
        @desc: cancels a pending session on remote or local host"""
        url = f"http://{host_ip}:{self.app_port}/cancel"
        try:
            resp = requests.post(url, json={"session_id": session_id}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {}

    def getPendingConnect(self):
        """@param: none
        @return: dict with session data or empty dict
        @desc: checks local API for pending connection requests"""
        url = f"http://127.0.0.1:{self.app_port}/pending-connect"
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {}

    def getTree(self, host_ip: str, session_id: str, path: str = None, depth: int = 1, hidden: bool = False):
        """@param host_ip: IP address of the host to fetch tree from
        @param session_id: verified session identifier
        @param path: optional directory path to browse
        @param depth: tree depth level
        @param hidden: whether to include hidden files
        @return: dict representing directory tree or error
        @desc: fetches remote directory tree via session-authenticated API"""
        url = f"http://{host_ip}:{self.app_port}/tree"
        body = {"session_id": session_id, "depth": depth, "hidden": hidden}
        if path:
            body["path"] = path
        try:
            resp = requests.post(url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"error": "connection error"}

    def disconnect(self, host_ip: str, session_id: str):
        """@param host_ip: IP address of the host owning the session
        @param session_id: session identifier to destroy
        @return: dict with disconnected key
        @desc: destroys session on remote host"""
        url = f"http://{host_ip}:{self.app_port}/disconnect"
        try:
            resp = requests.post(url, json={"session_id": session_id}, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {}

    def printNetworkInfo(self):
        """@param: none
        @return: dictionary with network interface information
        @desc: prints and returns network interface details"""
        iface = str(conf.iface)
        ip = get_if_addr(iface)
        net = ipaddress.ip_interface(f"{ip}/24").network
        info = {
            "iface": iface,
            "ip": ip,
            "subnet": str(net),
        }
        print(json.dumps(info, indent=2))
        return info

    def getNetworkInfo(self):
        """@param: none
        @return: dictionary with network interface information
        @desc: returns network interface details without printing"""
        iface = str(conf.iface)
        ip = get_if_addr(iface)
        net = ipaddress.ip_interface(f"{ip}/24").network
        return {
            "iface": iface,
            "ip": ip,
            "subnet": str(net),
        }