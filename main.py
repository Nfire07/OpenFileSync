"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: TUI application for OpenFileSync with network host discovery and status monitoring
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button, Input
from textual.screen import ModalScreen
from textual.containers import Container, HorizontalScroll, Vertical, VerticalScroll
from textual.binding import Binding
from rich.text import Text
from pathlib import Path
from ipaddress import ip_address
from modules.KnownHosts import Host
from modules.Network import Network
from modules.Api import OpenFileSyncApi
from modules.Logger import setup_logger, log_exception, log_expected_error, install_global_handler, setup_textual_logger
import threading


logger = setup_logger()


def hostStatus(status: str) -> Text:
    """@param status: the host status string
    @return: styled Text with colored dot
    @desc: returns styled text with colored dot based on host status"""
    if status == "active":
        color = "bold green"
    elif status == "loading":
        color = "bold cyan"
    else:
        color = "bold yellow"
    return Text("◉ ", style=color)


class OtpModal(ModalScreen):
    CSS = """
    OtpModal {
        align: center middle;
    }
    #otp-dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $primary;
        background: $surface;
    }
    #otp-title {
        text-align: center;
        width: 100%;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    #otp-code {
        text-align: center;
        width: 100%;
        height: 3;
        content-align: center middle;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #otp-from {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    #otp-buttons {
        width: 100%;
        height: auto;
        layout: horizontal;
        align: center middle;
    }
    #otp-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(self, session_id: str, otp: int, from_ip: str, network: Network, **kwargs):
        """@param session_id: unique session identifier
        @param otp: the OTP code to display
        @param from_ip: IP address of the connecting host
        @param network: Network instance for API calls
        @return: none
        @desc: initializes OtpModal with connection request data"""
        super().__init__(**kwargs)
        self.session_id = session_id
        self.otp = otp
        self.from_ip = from_ip
        self.network = network

    def compose(self) -> ComposeResult:
        """@param: none
        @return: ComposeResult with modal widgets
        @desc: composes the OTP modal with code display and action buttons"""
        with Container(id="otp-dialog"):
            yield Static("Connection Request", id="otp-title")
            yield Static(f"  {self.otp:02d}  ", id="otp-code")
            yield Static(f"from {self.from_ip}", id="otp-from")
            with Container(id="otp-buttons"):
                yield Button("Accept", variant="success", id="btn-accept")
                yield Button("Reject", variant="error", id="btn-reject")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """@param event: Button.Pressed event from the modal
        @return: none
        @desc: handles accept/reject button press"""
        if event.button.id == "btn-reject":
            self._cancel_session()
        self.dismiss(result=event.button.id)

    def _cancel_session(self):
        """@param: none
        @return: none
        @desc: cancels this session via local API"""
        self.network.cancelSession("127.0.0.1", self.session_id)


class ConnectOtpModal(ModalScreen):
    CSS = """
    ConnectOtpModal {
        align: center middle;
    }
    #connect-dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        border: thick $success;
        background: $surface;
    }
    #connect-title {
        text-align: center;
        width: 100%;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    #connect-target {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    #connect-hint {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    #otp-input {
        width: 100%;
        margin-bottom: 1;
    }
    #connect-buttons {
        width: 100%;
        layout: horizontal;
        align: center middle;
    }
    #connect-buttons Button {
        margin: 0 1;
    }
    #connect-status {
        text-align: center;
        width: 100%;
        color: $error;
        margin-top: 0;
    }
    """

    def __init__(self, session_id: str, target_ip: str, network: Network, **kwargs):
        """@param session_id: unique session identifier
        @param target_ip: IP address of the target host
        @param network: Network instance for API calls
        @return: none
        @desc: initializes ConnectOtpModal with session and target data"""
        super().__init__(**kwargs)
        self.session_id = session_id
        self.target_ip = target_ip
        self.network = network

    def compose(self) -> ComposeResult:
        """@param: none
        @return: ComposeResult with modal widgets
        @desc: composes the OTP input modal with text field and action buttons"""
        with Container(id="connect-dialog"):
            yield Static("Connection Request", id="connect-title")
            yield Static(f"to {self.target_ip}", id="connect-target")
            yield Static("Enter the OTP shown on the remote host", id="connect-hint")
            yield Input(placeholder="Enter OTP...", id="otp-input", max_length=3)
            yield Static("", id="connect-status")
            with Container(id="connect-buttons"):
                yield Button("Submit", variant="success", id="btn-submit")
                yield Button("Cancel", variant="error", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """@param event: Button.Pressed event from the modal
        @return: none
        @desc: handles submit/cancel button press"""
        if event.button.id == "btn-cancel":
            self._cancel_session()
            self.dismiss(result="cancelled")
        elif event.button.id == "btn-submit":
            self._submit_otp()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """@param event: Input.Submitted event from the text field
        @return: none
        @desc: handles enter key press on the OTP input"""
        self._submit_otp()

    def _submit_otp(self):
        """@param: none
        @return: none
        @desc: validates and sends OTP to target host for verification"""
        otp_text = self.query_one("#otp-input", Input).value.strip()
        if not otp_text or not otp_text.isdigit():
            self.query_one("#connect-status", Static).update("Please enter a valid number")
            return
        result = self.network.sendOtp(self.target_ip, self.session_id, int(otp_text))
        if result.get("verified"):
            self.dismiss(result="verified")
        else:
            self.query_one("#connect-status", Static).update(result.get("error", "Verification failed"))

    def _cancel_session(self):
        """@param: none
        @return: none
        @desc: cancels this session on the remote host"""
        self.network.cancelSession(self.target_ip, self.session_id)


class HostItem(Static):
    def __init__(self, client_ip: str, host_data: dict, network: Network, **kwargs):
        """@param client_ip: local client IP address string
        @param host_data: dictionary containing host information
        @param network: Network instance for API checks
        @return: none
        @desc: initializes HostItem with host data and network reference"""
        super().__init__(**kwargs)
        self.client_ip = client_ip.strip()
        self.host_data = host_data
        self.network = network
        self.api_status = "loading"

    def on_mount(self) -> None:
        """@param: none
        @return: none
        @desc: renders initial state and starts API status check worker"""
        self._update_content()
        self.run_worker(self._check_api_status, thread=True)

    def _check_api_status(self):
        """@param: none
        @return: none
        @desc: checks API status for the host asynchronously"""
        try:
            ipv4 = (self.host_data.get("ipv4", "") or "").strip()
            if ipv4:
                result = self.network.getHostInformation(ipv4)
                self.api_status = result.get("status", "inactive")
        except Exception:
            self.api_status = "inactive"
        self.app.call_from_thread(self._update_content)

    def _update_content(self):
        """@param: none
        @return: none
        @desc: updates the host item display with API status indicator"""
        ipv4 = (self.host_data.get("ipv4", "") or "").strip()
        ipv6 = self.host_data.get("ipv6") or "-"
        hostname = self.host_data.get("hostname") or "(Unknown)"

        try:
            dot_style = "bold cyan" if ip_address(ipv4) == ip_address(self.client_ip) else "bold green"
        except ValueError:
            dot_style = "bold green"

        content = Text()
        content.append(hostStatus(self.api_status))
        content.append(f"{ipv4} ", style="bold")
        content.append(f"[{ipv6}] ", style="yellow")
        content.append(f"{hostname} ", style="white")
        self.update(content)

    def on_click(self) -> None:
        """@param: none
        @return: none
        @desc: initiates connection to remote host and shows OTP input modal"""
        if self.api_status != "active":
            return
        target_ip = (self.host_data.get("ipv4", "") or "").strip()
        if not target_ip:
            return
        data = self.network.connect(target_ip, self.client_ip)
        if "session_id" in data:
            self._last_session_id = data["session_id"]
            modal = ConnectOtpModal(
                session_id=data["session_id"],
                target_ip=target_ip,
                network=self.network,
            )
            self.app.push_screen(modal, self._on_connect_result)

    def _on_connect_result(self, result: str):
        """@param result: modal dismiss result string
        @return: none
        @desc: handles connect modal result and activates filesystem panel"""
        if result == "verified":
            target_ip = (self.host_data.get("ipv4", "") or "").strip()
            self.app.active_session = {
                "session_id": self._last_session_id,
                "remote_ip": target_ip,
                "role": "initiator",
            }
            fs = self.app.query_one("#fs-panel", FilesystemPanel)
            fs.connect(self._last_session_id, target_ip)


class DirectoryEntry(Static):
    def __init__(self, entry: dict, network: Network, session_id: str, remote_ip: str, panel, **kwargs):
        """@param entry: dict with name, path, type, and optional children
        @param network: Network instance for API calls
        @param session_id: verified session identifier
        @param remote_ip: IP address of the remote host
        @param panel: reference to the parent FilesystemPanel
        @return: none
        @desc: initializes a directory or file entry for the filesystem panel"""
        super().__init__(**kwargs)
        self.entry = entry
        self.network = network
        self.session_id = session_id
        self.remote_ip = remote_ip
        self.panel = panel
        self.is_dir = entry.get("type") == "directory"

    def on_mount(self) -> None:
        """@param: none
        @return: none
        @desc: renders the entry with icon and name"""
        icon = "📁" if self.is_dir else "📄"
        name = self.entry.get("name", "")
        style = "bold" if self.is_dir else ""
        content = Text()
        content.append(f" {icon} {name}", style=style)
        self.update(content)

    def on_click(self) -> None:
        """@param: none
        @return: none
        @desc: navigates into directory when clicked"""
        if not self.is_dir:
            return
        path = self.entry.get("path")
        if not path:
            return
        self.panel.load_tree(path)


class FilesystemPanel(Vertical):
    CSS = """
    FilesystemPanel {
        width: 100%;
        height: 100%;
    }
    #fs-header {
        width: 100%;
        height: auto;
        text-style: bold;
        padding: 0 1;
        border-bottom: solid $primary;
    }
    #fs-entries {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    DirectoryEntry {
        height: auto;
        width: 100%;
        text-wrap: nowrap;
        padding: 0 1;
    }
    DirectoryEntry:hover {
        background: $accent 15%;
    }
    """

    def __init__(self, network: Network, **kwargs):
        """@param network: Network instance for API calls
        @return: none
        @desc: initializes FilesystemPanel with network reference"""
        super().__init__(**kwargs)
        self.network = network
        self.session_id = None
        self.remote_ip = None
        self.current_path = None
        self._header = Static("Not connected", id="fs-header")
        self._entries = VerticalScroll(id="fs-entries")

    def compose(self) -> ComposeResult:
        """@param: none
        @return: ComposeResult with header and entry list
        @desc: composes the filesystem panel layout"""
        yield self._header
        yield self._entries

    def connect(self, session_id: str, remote_ip: str):
        """@param session_id: verified session identifier
        @param remote_ip: IP address of the remote host
        @return: none
        @desc: activates the panel and loads the root directory"""
        self.session_id = session_id
        self.remote_ip = remote_ip
        self.load_tree(None)

    def disconnect(self):
        """@param: none
        @return: none
        @desc: clears the panel and resets connection state"""
        self.session_id = None
        self.remote_ip = None
        self.current_path = None
        self._header.update("Not connected")
        for child in list(self._entries.children):
            child.remove()

    def load_tree(self, path: str = None):
        """@param path: directory path to load, or None for home
        @return: none
        @desc: fetches and renders directory contents from remote host"""
        if not self.session_id or not self.remote_ip:
            return
        for child in list(self._entries.children):
            child.remove()
        self._header.update(f"Loading {path or '~'}...")
        self.run_worker(self._fetch_tree, path, thread=True)

    def _fetch_tree(self, path: str = None):
        """@param path: directory path to fetch
        @return: none
        @desc: fetches tree data from remote host in background thread"""
        data = self.network.getTree(self.remote_ip, self.session_id, path)
        self.app.call_from_thread(self._render_tree, data, path)

    def _render_tree(self, data: dict, path: str = None):
        """@param data: tree dict from API
        @param path: the path that was loaded
        @return: none
        @desc: renders the fetched tree entries into the scroll container"""
        if "error" in data:
            self._header.update(f"Error: {data['error']}")
            return
        display_path = data.get("path", path or "~")
        self.current_path = display_path
        self._header.update(f" {display_path}")
        children = data.get("children", [])
        dirs = [c for c in children if c.get("type") == "directory"]
        files = [c for c in children if c.get("type") == "file"]
        if self.current_path and self.current_path != str(Path.home()):
            back = {"name": "..", "path": str(Path(self.current_path).parent), "type": "directory"}
            self._entries.mount(DirectoryEntry(back, self.network, self.session_id, self.remote_ip, self))
        for entry in dirs:
            self._entries.mount(DirectoryEntry(entry, self.network, self.session_id, self.remote_ip, self))
        for entry in files:
            self._entries.mount(DirectoryEntry(entry, self.network, self.session_id, self.remote_ip, self))


class AvailableHosts(Vertical):
    def __init__(self, client_ip: str, **kwargs):
        """@param client_ip: local client IP address string
        @return: none
        @desc: initializes AvailableHosts with client IP and network instance"""
        super().__init__(**kwargs)
        self.client_ip = client_ip.strip()
        self.network = Network()
        self._message = Static("Press S to scan network...")

    def compose(self):
        """@param: none
        @return: ComposeResult with message widget
        @desc: yields the internal message static widget"""
        yield self._message

    def start_scan(self) -> None:
        """@param: none
        @return: none
        @desc: starts network scan worker to discover available hosts"""
        self._message.update("Searching hosts...")
        self.run_worker(self.refresh_hosts, thread=True, exclusive=True)

    def refresh_hosts(self):
        """@param: none
        @return: list of discovered host dictionaries
        @desc: retrieves available hosts from network discovery"""
        return self.network.getAvailableHosts()

    def on_worker_state_changed(self, event) -> None:
        if event.worker.is_finished:
            try:
                hosts = event.worker.result
            except Exception as exc:
                log_exception(logger, exc, "Network scan worker")
                self._message.update("Scan failed")
                return

            for child in list(self.children):
                if isinstance(child, HostItem):
                    child.remove()

            if not hosts:
                self._message.update("No Host found")
                return

            self._message.display = False
            for host in hosts:
                self.mount(HostItem(self.client_ip, host, self.network))


class OpenFileSyncApp(App):
    CSS_PATH = "./assets/main.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit Application"),
        Binding("s", "scan", "Scan Network"),
        Binding("k", "kill_connection", "Disconnect"),
    ]

    host = Host.create()

    def __init__(self, *args, **kwargs):
        """@param args: positional arguments for App
        @param kwargs: keyword arguments for App
        @return: none
        @desc: initializes app with network, host state, and connection tracking"""
        self.network = Network()
        self.network_info = self.network.getNetworkInfo()
        self.host_state = {"status": "loading"}
        self._pending_shown = set()
        self.active_session = None
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        """@param: none
        @return: ComposeResult with all UI widgets
        @desc: composes the TUI layout with header, host info, and panels"""
        yield Header(show_clock=True)

        with Container(id="host-info"):
            yield Static("", id="host-status", markup=True)

        with Container(id="main", classes="row"):
            with Container(id="available_hosts"):
                yield HorizontalScroll(id="hosts-scroll")
            with Container(id="filesystem"):
                yield FilesystemPanel(self.network, id="fs-panel")

        yield Footer()

    def on_mount(self) -> None:
        """@param: none
        @return: none
        @desc: updates layout, checks host API status, mounts host panel, and starts polling"""
        self._update_layout()

        self.host_state = self.network.getHostInformation(self.network_info["ip"])
        self._update_host_bar()

        scroll = self.query_one("#hosts-scroll", HorizontalScroll)
        self.available_hosts = AvailableHosts(self.network_info["ip"])
        scroll.mount(self.available_hosts)

        self.set_interval(2.0, self._poll_pending_connect)

    def _update_host_bar(self) -> None:
        """@param: none
        @return: none
        @desc: updates host info bar with colored status indicator"""
        status_widget = self.query_one("#host-status", Static)
        state = self.host_state["status"]

        if state == "active":
            color = "bold green"
        elif state == "loading":
            color = "bold cyan"
        else:
            color = "bold yellow"

        status_widget.update(
            f"[{color}]◉[/] [bold]{self.host.name}[/] - {self.network_info['ip']} : [yellow]{self.host.id}[/]"
        )

    def _poll_pending_connect(self) -> None:
        """@param: none
        @return: none
        @desc: polls local API for pending connection requests directed to this host"""
        data = self.network.getPendingConnect()
        if not data or "session_id" not in data:
            return
        if data.get("target_ip") != self.network_info["ip"]:
            return
        sid = data["session_id"]
        if sid in self._pending_shown:
            return
        self._pending_shown.add(sid)
        self._last_otp_session_id = sid
        self._last_otp_from_ip = data["from_ip"]
        modal = OtpModal(
            session_id=sid,
            otp=data["otp"],
            from_ip=data["from_ip"],
            network=self.network,
        )
        self.push_screen(modal, self._on_otp_result)

    def _on_otp_result(self, result: str):
        """@param result: modal dismiss result string
        @return: none
        @desc: handles OTP modal result and activates filesystem panel for target"""
        if result == "btn-accept":
            session_id = self._last_otp_session_id
            from_ip = self._last_otp_from_ip
            self.active_session = {
                "session_id": session_id,
                "remote_ip": from_ip,
                "role": "target",
            }
            fs = self.query_one("#fs-panel", FilesystemPanel)
            fs.connect(session_id, from_ip)

    def action_kill_connection(self) -> None:
        """@param: none
        @return: none
        @desc: disconnects active session on both sides and resets filesystem panel"""
        if not self.active_session:
            return
        sid = self.active_session["session_id"]
        remote_ip = self.active_session["remote_ip"]
        self.network.disconnect(remote_ip, sid)
        self.network.cancelSession("127.0.0.1", sid)
        self.active_session = None
        self._pending_shown.discard(sid)
        fs = self.query_one("#fs-panel", FilesystemPanel)
        fs.disconnect()

    def action_scan(self) -> None:
        """@param: none
        @return: none
        @desc: triggers network scan to discover available hosts"""
        self.available_hosts.start_scan()

    def on_resize(self, event) -> None:
        """@param event: resize event from Textual
        @return: none
        @desc: updates layout when terminal size changes"""
        self.call_after_refresh(self._update_layout)

    def _update_layout(self) -> None:
        """@param: none
        @return: none
        @desc: adjusts layout based on terminal width threshold"""
        main = self.query_one("#main")
        if self.size.width < 90:
            main.remove_class("row")
            main.add_class("column")
        else:
            main.remove_class("column")
            main.add_class("row")


if __name__ == "__main__":
    install_global_handler(logger)
    setup_textual_logger()
    logger.info("Application starting")

    try:
        api = OpenFileSyncApi()
        thread = threading.Thread(target=api.run, daemon=True)
        thread.start()
        logger.info("API server started on port 8010")
        OpenFileSyncApp().run()
    except Exception as exc:
        log_exception(logger, exc, "Application main")
        raise