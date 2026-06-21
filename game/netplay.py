"""
CyberLayerQuest — Multiplayer network layer
TCP peer-to-peer: host listens on PORT_TCP, client connects.
UDP broadcast: host announces room so clients auto-discover on LAN / localhost.
"""

import socket
import threading
import json
import queue
import time
import hashlib

PORT_TCP = 12345
PORT_UDP = 12346
BCAST_INTERVAL = 1.5   # seconds between UDP announces


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _subnet_broadcast(local_ip: str) -> str:
    parts = local_ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".255"
    return "192.168.1.255"


def _hash_pass(p: str) -> str:
    return hashlib.md5(p.encode()).hexdigest()[:10]


def _recv_line(sock: socket.socket, timeout: float = 15.0) -> str | None:
    """Read until newline from a socket."""
    sock.settimeout(timeout)
    buf = b""
    try:
        while b"\n" not in buf:
            chunk = sock.recv(1)
            if not chunk:
                return None
            buf += chunk
        return buf.decode("utf-8", errors="ignore").strip()
    except Exception:
        return None
    finally:
        sock.settimeout(None)


class NetworkManager:
    """
    Thread-safe network manager.

    Usage (host):
        net = NetworkManager()
        net.host("SALA1", "senha")
        # poll net.status until "connected"
        net.send({"type": "start", "model": "osi"})

    Usage (client):
        net = NetworkManager()
        net.join("SALA1", "senha")
        # poll net.status until "connected"
        for msg in net.poll():
            ...
    """

    def __init__(self):
        self.mode: str = ""          # "host" | "client"
        self.status: str = "idle"    # idle | hosting | searching | connected | error | disconnected
        self.error_msg: str = ""
        self.my_ip: str = _get_local_ip()
        self.peer_ip: str = ""

        self._tcp_server: socket.socket | None = None
        self._peer_conn: socket.socket | None = None

        self._recv_q: queue.Queue = queue.Queue()
        self._send_q: queue.Queue = queue.Queue()

        self._stop_bcast = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def host(self, code: str, password: str):
        self.mode = "host"
        self.status = "hosting"
        self._code = code
        self._pass_hash = _hash_pass(password)
        t = threading.Thread(target=self._host_thread, daemon=True)
        t.start()

    def join(self, code: str, password: str):
        self.mode = "client"
        self.status = "searching"
        self._code = code
        self._pass_hash = _hash_pass(password)
        t = threading.Thread(target=self._join_thread, daemon=True)
        t.start()

    def send(self, msg: dict):
        if self._peer_conn and self.status == "connected":
            self._send_q.put(msg)

    def poll(self) -> list[dict]:
        msgs = []
        while not self._recv_q.empty():
            try:
                msgs.append(self._recv_q.get_nowait())
            except queue.Empty:
                break
        return msgs

    def close(self):
        self._stop_bcast.set()
        self._send_q.put(None)  # signal sender to stop
        for s in (self._peer_conn, self._tcp_server):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self.status = "idle"

    # ------------------------------------------------------------------
    # Host thread
    # ------------------------------------------------------------------

    def _host_thread(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.settimeout(90)
            srv.bind(("0.0.0.0", PORT_TCP))
            srv.listen(1)
            self._tcp_server = srv
        except Exception as e:
            self.status = "error"
            self.error_msg = f"Porta {PORT_TCP} em uso: {e}"
            return

        # UDP broadcast thread
        threading.Thread(target=self._broadcast_loop, daemon=True).start()

        try:
            conn, addr = srv.accept()
            self.peer_ip = addr[0]
        except socket.timeout:
            self.status = "error"
            self.error_msg = "Nenhum jogador entrou (tempo esgotado)"
            return
        except Exception as e:
            if self.status != "idle":
                self.status = "error"
                self.error_msg = str(e)
            return
        finally:
            self._stop_bcast.set()

        # Handshake
        line = _recv_line(conn)
        if not line:
            self.status = "error"
            self.error_msg = "Cliente desconectou durante handshake"
            return
        try:
            msg = json.loads(line)
        except Exception:
            self.status = "error"
            self.error_msg = "Handshake inválido"
            return

        if msg.get("type") != "join" or msg.get("code") != self._code or msg.get("ph") != self._pass_hash:
            conn.sendall((json.dumps({"type": "error", "msg": "Código ou senha incorretos"}) + "\n").encode())
            conn.close()
            self.status = "error"
            self.error_msg = "Jogador rejeitado (código/senha errados)"
            return

        conn.sendall((json.dumps({"type": "welcome", "char": "black"}) + "\n").encode())
        self._peer_conn = conn
        self.status = "connected"
        self._start_io(conn)

    def _broadcast_loop(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = json.dumps({
            "type": "room_announce",
            "code": self._code,
            "ph":   self._pass_hash,
            "ip":   self.my_ip,
        }).encode()
        targets = ["255.255.255.255", _subnet_broadcast(self.my_ip), "127.0.0.1"]
        while not self._stop_bcast.is_set():
            for addr in targets:
                try:
                    udp.sendto(payload, (addr, PORT_UDP))
                except Exception:
                    pass
            time.sleep(BCAST_INTERVAL)
        udp.close()

    # ------------------------------------------------------------------
    # Client thread
    # ------------------------------------------------------------------

    def _join_thread(self):
        host_ip = self._discover_host()
        if not host_ip:
            if self.status != "idle":
                self.status = "error"
                self.error_msg = "Sala não encontrada. Verifique código/senha e se o host está ativo."
            return

        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.settimeout(10)
            conn.connect((host_ip, PORT_TCP))
            conn.settimeout(None)
        except Exception as e:
            self.status = "error"
            self.error_msg = f"Falha ao conectar em {host_ip}: {e}"
            return

        # Handshake
        conn.sendall((json.dumps({
            "type": "join",
            "code": self._code,
            "ph":   self._pass_hash,
        }) + "\n").encode())

        line = _recv_line(conn)
        if not line:
            self.status = "error"
            self.error_msg = "Host desconectou"
            return
        try:
            resp = json.loads(line)
        except Exception:
            self.status = "error"
            self.error_msg = "Resposta inválida do host"
            return

        if resp.get("type") != "welcome":
            self.status = "error"
            self.error_msg = resp.get("msg", "Conexão recusada pelo host")
            return

        self._peer_conn = conn
        self.peer_ip = host_ip
        self.status = "connected"
        self._start_io(conn)

    def _discover_host(self, timeout: float = 15.0) -> str | None:
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            udp.bind(("0.0.0.0", PORT_UDP))
        except Exception as e:
            self.error_msg = f"Erro ao ouvir UDP: {e}"
            return None

        udp.settimeout(1.0)
        deadline = time.time() + timeout
        found_ip = None
        while time.time() < deadline and self.status == "searching":
            try:
                data, addr = udp.recvfrom(1024)
                msg = json.loads(data.decode())
                if (msg.get("type") == "room_announce"
                        and msg.get("code") == self._code
                        and msg.get("ph") == self._pass_hash):
                    # Prefer the IP in the packet; fall back to socket addr
                    found_ip = msg.get("ip") or addr[0]
                    break
            except socket.timeout:
                continue
            except Exception:
                continue
        udp.close()
        return found_ip

    # ------------------------------------------------------------------
    # I/O threads (shared by host and client after handshake)
    # ------------------------------------------------------------------

    def _start_io(self, conn: socket.socket):
        threading.Thread(target=self._recv_loop, args=(conn,), daemon=True).start()
        threading.Thread(target=self._send_loop, args=(conn,), daemon=True).start()

    def _recv_loop(self, conn: socket.socket):
        buf = ""
        while True:
            try:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            self._recv_q.put(json.loads(line))
                        except Exception:
                            pass
            except Exception:
                break
        if self.status == "connected":
            self.status = "disconnected"
            self._recv_q.put({"type": "peer_disconnect"})

    def _send_loop(self, conn: socket.socket):
        while True:
            try:
                msg = self._send_q.get(timeout=0.5)
                if msg is None:
                    break
                conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            except queue.Empty:
                continue
            except Exception:
                break
