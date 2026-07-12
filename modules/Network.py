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