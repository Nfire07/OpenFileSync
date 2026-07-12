"""
Author: Mele Nicolo' Emanuele
Date: July 11, 2026
License: MIT
Description: TUI application for OpenFileSync with network host discovery and status monitoring
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.screen import ModalScreen
from textual.containers import Container, HorizontalScroll, Vertical
from textual.binding import Binding
from rich.text import Text
from ipaddress import ip_address
from modules.KnownHosts import Host
from modules.Network import Network
from modules.Api import OpenFileSyncApi
from modules.Logger import setup_logger, log_exception, log_expected_error, install_global_handler, setup_textual_logger
import threading
import requests


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

    def __init__(self, session_id: str, otp: int, from_ip: str, **kwargs):
        """@param session_id: unique session identifier
        @param otp: the OTP code to display
        @param from_ip: IP address of the connecting host
        @return: none
        @desc: initializes OtpModal with connection request data"""
        super().__init__(**kwargs)
        self.session_id = session_id
        self.otp = otp
        self.from_ip = from_ip

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
        @desc: sends cancel request to API for this session"""
        try:
            requests.post(
                "http://127.0.0.1:8010/cancel",
                json={"session_id": self.session_id},
                timeout=2,
            )
        except requests.RequestException:
            pass


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
    ]

    host = Host.create()

    def __init__(self, *args, **kwargs):
        """@param args: positional arguments for App
        @param kwargs: keyword arguments for App
        @return: none
        @desc: initializes app with network and host state"""
        self.network = Network()
        self.network_info = self.network.getNetworkInfo()
        self.host_state = {"status": "loading"}
        self.api_base = f"http://127.0.0.1:{8010}"
        self._pending_shown = set()
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
                yield Static("Filesystem")

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
        @desc: polls API for pending connection requests and shows OTP modal"""
        try:
            resp = requests.get(f"{self.api_base}/pending-connect", timeout=1.5)
            data = resp.json()
            if not data or "session_id" not in data:
                return
            sid = data["session_id"]
            if sid in self._pending_shown:
                return
            self._pending_shown.add(sid)
            self.push_screen(OtpModal(
                session_id=sid,
                otp=data["otp"],
                from_ip=data["from_ip"],
            ))
        except requests.RequestException:
            pass

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