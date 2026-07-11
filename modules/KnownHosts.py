"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: Persistent host registry for storing and managing known network hosts
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from modules.Logger import setup_logger, log_exception


logger = setup_logger()


KNOWN_HOSTS_FILE = Path.home() / ".known_hosts.json"


@dataclass(slots=True)
class Host:
    id: str
    name: str
    last_seen: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls) -> "Host":
        """@param: none
        @return: new Host instance
        @desc: creates a new Host with UUID and hostname"""
        return cls(
            id=str(uuid.uuid4()),
            name=Host.getHostname()
        )

    @staticmethod
    def getHostname() -> str:
        """@param: none
        @return: hostname string
        @desc: retrieves system hostname via subprocess"""
        subprocess = __import__("subprocess")
        try:
            result = subprocess.run(
                ["hostname"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as exc:
            log_exception(logger, exc, "Hostname retrieval")
            return "Unknown"



class KnownHosts:

    def __init__(self) -> None:
        """@param: none
        @return: none
        @desc: initializes KnownHosts and loads existing hosts"""
        self._hosts: dict[str, Host] = {}
        self.load()

    def add(self, host: Host) -> None:
        """@param host: Host instance to add
        @return: none
        @desc: adds host to registry and saves to file"""
        self._hosts[host.id] = host
        self.save()

    def remove(self, host_id: str) -> bool:
        """@param host_id: ID of host to remove
        @return: True if removed, False if not found
        @desc: removes host from registry by ID"""
        if host_id not in self._hosts:
            return False

        del self._hosts[host_id]
        self.save()
        return True

    def get(self, host_id: str) -> Host | None:
        """@param host_id: ID of host to retrieve
        @return: Host instance or None
        @desc: retrieves host by ID from registry"""
        return self._hosts.get(host_id)

    def get_by_name(self, name: str) -> Host | None:
        """@param name: hostname to search for
        @return: Host instance or None
        @desc: retrieves host by hostname from registry"""
        return next(
            (host for host in self._hosts.values() if host.name == name),
            None
        )

    def all(self) -> list[Host]:
        """@param: none
        @return: list of all Host instances
        @desc: returns all known hosts as list"""
        return list(self._hosts.values())

    def update_seen(self, host_id: str) -> None:
        """@param host_id: ID of host to update
        @return: none
        @desc: updates last_seen timestamp for host"""
        host = self.get(host_id)

        if host is None:
            return

        host.last_seen = datetime.now()
        self.save()

    def __len__(self) -> int:
        """@param: none
        @return: number of known hosts
        @desc: returns count of hosts in registry"""
        return len(self._hosts)

    def __iter__(self):
        """@param: none
        @return: iterator over Host instances
        @desc: returns iterator for iterating over hosts"""
        return iter(self._hosts.values())

    def load(self) -> None:
        """@param: none
        @return: none
        @desc: loads hosts from JSON file into registry"""
        self._hosts.clear()

        if not KNOWN_HOSTS_FILE.exists():
            return

        try:
            with KNOWN_HOSTS_FILE.open(
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            for item in data:
                item["last_seen"] = datetime.fromisoformat(
                    item["last_seen"]
                )

                host = Host(**item)
                self._hosts[host.id] = host

        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError
        ) as exc:
            log_exception(logger, exc, "Loading known hosts file")
            self._hosts.clear()

    def save(self) -> None:
        """@param: none
        @return: none
        @desc: saves hosts registry to JSON file"""
        data = []

        for host in self._hosts.values():
            item = asdict(host)
            item["last_seen"] = host.last_seen.isoformat()
            data.append(item)

        with KNOWN_HOSTS_FILE.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )