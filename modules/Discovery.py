"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: Network discovery module using arp-scan for host detection
"""
import json
import subprocess
import sys
from pathlib import Path
from modules.Logger import setup_logger, log_exception


logger = setup_logger()

class Discovery:
    def __init__(self):
        """@param: none
        @return: none
        @desc: initializes Discovery with helper script path"""
        self.helper = Path(__file__).with_name("DiscoveryWorkerRunner.py")

    def scan(self):
        """@param: none
        @return: list of discovered host dictionaries
        @desc: runs arp-scan via helper script with elevated privileges"""
        try:
            result = subprocess.run(
                ["pkexec", sys.executable, str(self.helper)],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            log_exception(logger, exc, "Network discovery scan")
            return []