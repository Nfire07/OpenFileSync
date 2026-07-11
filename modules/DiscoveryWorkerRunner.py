"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: ARP scan worker runner for discovering hosts on local network
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_arp_scan(iface=None):
    """@param iface: network interface name (optional)
    @return: raw arp-scan output string
    @desc: executes arp-scan command with sudo privileges"""
    cmd = [
        "arp-scan",
        "--localnet",
        "--plain",
        "--format=${ip}\t${mac}\t${vendor}"
    ]
    if iface:
        cmd = [
            "arp-scan",
            "-I",
            iface,
            "--localnet",
            "--plain",
            "--format=${ip}\t${mac}\t${vendor}"
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def parse_arp_scan(output):
    """@param output: raw arp-scan output string
    @return: list of host dictionaries with ipv4, ipv6, hostname
    @desc: parses arp-scan output into structured host data"""
    hosts = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[0]):
            ipv4 = parts[0].strip()
            ipv6 = parts[1].strip() if parts[1].strip() else None
            hostname = parts[2].strip() if parts[2].strip() else None

            hosts.append({
                "ipv4": ipv4,
                "ipv6": ipv6,
                "hostname": hostname,
            })
    return hosts


if __name__ == "__main__":
    out = run_arp_scan()
    print(json.dumps(parse_arp_scan(out), ensure_ascii=False))