"""Capture and Show driven through the real proxy over real sockets.

A stand-in Demonware server plays the part of the content server, and
proxy._connect_upstream is redirected to it - everything else (request
parsing, emblem matching, mode handling, writing captures, replaying a
selection) is the actual code path a console goes through.

Run from the repo root:

    python -m unittest discover -s tests
"""
import http.server
import os
import shutil
import socket
import struct
import sys
import tempfile
import threading
import unittest

_TMP = tempfile.mkdtemp(prefix="bo2toolkit-e2e-")
os.environ["BO2_TOOLKIT_DATA_DIR"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emblemtool import broadcast, config, consoles, proxy, state, storage  # noqa: E402

EMBLEM_BODY = b"".join(
    struct.pack("<H", 137 if i < 3 else 65535) + b"\x00\x00"
    + struct.pack("<9f", 1.0, 0.5, 0.25, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    + b"\x00\x00\x00\x00"
    for i in range(32)
)
OTHER_BODY = b"not an emblem"

EMBLEM_PATH = "/u51b08745d269.slot_504"
EMBLEM_HOST = consoles.LEGACY_PS_HOST


class FakeDemonware(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # close after each response

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = EMBLEM_BODY if ".slot_" in self.path else OTHER_BODY
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ProxyEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeDemonware)
        cls.upstream_port = cls.upstream.server_address[1]
        threading.Thread(target=cls.upstream.serve_forever, daemon=True).start()

        # Every upstream connection lands on the stand-in server instead of the
        # real internet; the host the proxy *thinks* it's talking to is still
        # whatever the request line said, which is what matching keys off.
        cls._real_connect = proxy._connect_upstream
        proxy._connect_upstream = lambda host, port: cls._real_connect(
            "127.0.0.1", cls.upstream_port)

        cls.proxy_port = free_port()
        threading.Thread(
            target=proxy.serve, args=("127.0.0.1", cls.proxy_port), daemon=True
        ).start()
        cls._wait_for_proxy()

    @classmethod
    def _wait_for_proxy(cls):
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", cls.proxy_port), timeout=0.5):
                    return
            except OSError:
                pass
        raise RuntimeError("proxy never came up")

    @classmethod
    def tearDownClass(cls):
        proxy._connect_upstream = cls._real_connect
        cls.upstream.shutdown()
        cls.upstream.server_close()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        shutil.rmtree(config.SAVED_DIR, ignore_errors=True)
        state.write_state("PASSTHROUGH")

    def through_proxy(self, host, path):
        """One request through the proxy, exactly as a console sends it."""
        request = (
            f"GET http://{host}{path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: CallOfDuty\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        with socket.create_connection(("127.0.0.1", self.proxy_port), timeout=10) as s:
            s.sendall(request)
            chunks = []
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        return b"".join(chunks)

    def test_passthrough_leaves_the_response_alone(self):
        response = self.through_proxy(EMBLEM_HOST, EMBLEM_PATH)
        self.assertIn(b"200", response.split(b"\r\n")[0])
        self.assertTrue(response.endswith(EMBLEM_BODY))
        self.assertFalse(os.path.isdir(config.SAVED_DIR) and os.listdir(config.SAVED_DIR))

    def test_capture_writes_the_slot_and_still_serves_the_real_data(self):
        state.write_state("CAPTURE")
        response = self.through_proxy(EMBLEM_HOST, EMBLEM_PATH)
        self.assertTrue(response.endswith(EMBLEM_BODY), "console must still get real data")

        groups = storage.list_groups()
        self.assertEqual(groups, ["001"])
        self.assertEqual(storage.group_slots("001"), [504])
        self.assertEqual(storage.read_meta("001")["userhash"], "u51b08745d269")
        with open(os.path.join(storage.group_dir("001"), "slot_504.bin"), "rb") as f:
            self.assertTrue(f.read().endswith(EMBLEM_BODY))

    def test_capture_works_on_a_host_no_preset_knows(self):
        """The PS4 case: a SKU on a hostname nobody has captured before."""
        state.write_state("CAPTURE")
        self.through_proxy("ops2-ps4-cs.prod.demonware.net", EMBLEM_PATH)
        self.assertEqual(storage.group_slots("001"), [504])
        self.assertEqual(
            proxy.get_detected()["emblem_host"], "ops2-ps4-cs.prod.demonware.net")

    def test_show_replaces_the_response_with_the_selection(self):
        state.write_state("CAPTURE")
        self.through_proxy(EMBLEM_HOST, EMBLEM_PATH)
        broadcast.select_emblem("001", 504)

        replacement = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nMINE!"
        with open(os.path.join(storage.group_dir(config.ACTIVE_NAME), "selected.bin"), "wb") as f:
            f.write(replacement)

        state.write_state("INJECT")
        # A different slot number on purpose: the console asks for whichever of
        # its own slots it likes, and gets the selection regardless.
        self.assertEqual(self.through_proxy(EMBLEM_HOST, "/u00000000abcd.slot_1"), replacement)

    def test_show_falls_back_to_real_data_with_nothing_selected(self):
        broadcast.clear_selection()
        state.write_state("INJECT")
        self.assertTrue(self.through_proxy(EMBLEM_HOST, EMBLEM_PATH).endswith(EMBLEM_BODY))

    def test_non_emblem_demonware_traffic_is_untouched_in_every_mode(self):
        for mode in ("PASSTHROUGH", "CAPTURE", "INJECT"):
            with self.subTest(mode=mode):
                state.write_state(mode)
                response = self.through_proxy(EMBLEM_HOST, "/auth/login")
                self.assertTrue(response.endswith(OTHER_BODY))

    def test_unrelated_hosts_are_untouched_in_every_mode(self):
        for mode in ("PASSTHROUGH", "CAPTURE", "INJECT"):
            with self.subTest(mode=mode):
                state.write_state(mode)
                response = self.through_proxy("example.com", EMBLEM_PATH)
                self.assertTrue(response.endswith(EMBLEM_BODY))
                self.assertFalse(storage.list_groups(), "must not capture off-host traffic")


if __name__ == "__main__":
    unittest.main()
