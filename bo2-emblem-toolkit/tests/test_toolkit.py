"""Tests for the cross-console and cross-platform behaviour.

Run from the repo root:

    python -m unittest discover -s tests

Pillow is only needed for the rendering tests; they skip without it.
"""
import json
import os
import struct
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

# config reads this at import time, so it has to be set before emblemtool is
# imported - otherwise the tests would scribble in the real saved/ folder.
_TMP = tempfile.mkdtemp(prefix="bo2toolkit-tests-")
os.environ["BO2_TOOLKIT_DATA_DIR"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emblemtool import config, consoles, proxy, settings, storage  # noqa: E402
from emblemtool.shapes import render  # noqa: E402
from emblemtool.web import netinfo, server  # noqa: E402

LEGACY = consoles.LEGACY_PS_HOST
EMBLEM_PATH = "/u51b08745d269.slot_504?ts=1"


class TestEmblemRequestMatching(unittest.TestCase):
    """The PS4 fix: emblem traffic is recognised by its path, so a SKU on a
    hostname nobody has captured yet still works."""

    def test_auto_matches_the_legacy_ps3_host(self):
        userhash, slot = consoles.match_emblem_request(LEGACY, EMBLEM_PATH, "auto")
        self.assertEqual(userhash, "u51b08745d269")
        self.assertEqual(slot, 504)

    def test_auto_matches_an_unknown_console_host(self):
        for host in (
            "ops2-ps4-cs.prod.demonware.net",
            "ops2-ps5-cs.prod.demonware.net",
            "ops2-something-else-cs2.prod.demonware.net",
        ):
            with self.subTest(host=host):
                _, slot = consoles.match_emblem_request(host, EMBLEM_PATH, "auto")
                self.assertEqual(slot, 504, f"{host} should be recognised in auto mode")

    def test_auto_ignores_non_demonware_hosts(self):
        _, slot = consoles.match_emblem_request("example.com", EMBLEM_PATH, "auto")
        self.assertIsNone(slot)

    def test_auto_ignores_non_emblem_paths_on_demonware(self):
        for path in ("/", "/auth/login", "/u51b08745d269.profile"):
            with self.subTest(path=path):
                _, slot = consoles.match_emblem_request(LEGACY, path, "auto")
                self.assertIsNone(slot)

    def test_hostname_suffix_cannot_be_spoofed(self):
        _, slot = consoles.match_emblem_request(
            "demonware.net.evil.example", EMBLEM_PATH, "auto")
        self.assertIsNone(slot)

    def test_pinned_console_only_accepts_its_own_hosts(self):
        _, slot = consoles.match_emblem_request(LEGACY, EMBLEM_PATH, "ps5")
        self.assertEqual(slot, 504)
        _, slot = consoles.match_emblem_request(
            "ops2-xbl-cs.prod.demonware.net", EMBLEM_PATH, "ps5")
        self.assertIsNone(slot)

    def test_ps4_preset_accepts_both_candidate_hosts(self):
        for host in (LEGACY, "ops2-ps4-cs.prod.demonware.net"):
            with self.subTest(host=host):
                _, slot = consoles.match_emblem_request(host, EMBLEM_PATH, "ps4")
                self.assertEqual(slot, 504)

    def test_port_in_host_is_ignored(self):
        _, slot = consoles.match_emblem_request(LEGACY + ":80", EMBLEM_PATH, "auto")
        self.assertEqual(slot, 504)

    def test_unknown_console_key_falls_back_to_auto(self):
        self.assertEqual(consoles.get("nonsense").key, "auto")
        self.assertEqual(consoles.get(None).key, "auto")

    def test_guess_console_from_host(self):
        self.assertEqual(consoles.guess_console_from_host(LEGACY), "ps3")
        self.assertEqual(
            consoles.guess_console_from_host("ops2-xbl-cs.prod.demonware.net"), "xbox")
        self.assertEqual(
            consoles.guess_console_from_host("ops2-ps4-cs.prod.demonware.net"), "ps4")
        self.assertIsNone(consoles.guess_console_from_host("example.com"))

    def test_every_preset_is_well_formed(self):
        for entry in consoles.all_consoles():
            with self.subTest(console=entry["key"]):
                self.assertTrue(entry["name"])
                self.assertTrue(entry["proxy_steps"])


class TestRequestTargetParsing(unittest.TestCase):
    """Proxies normally get absolute-form request lines, but origin form with
    a Host header is legal and used to produce an empty host here."""

    def test_absolute_form(self):
        req = b"GET http://host.example/a/b HTTP/1.1\r\nHost: host.example\r\n\r\n"
        self.assertEqual(
            proxy._split_request_target("http://host.example/a/b", req),
            ("host.example", 80, "/a/b"),
        )

    def test_absolute_form_with_port(self):
        req = b"GET http://host.example:8080/a HTTP/1.1\r\n\r\n"
        self.assertEqual(
            proxy._split_request_target("http://host.example:8080/a", req),
            ("host.example", 8080, "/a"),
        )

    def test_origin_form_uses_the_host_header(self):
        req = b"GET /a/b HTTP/1.1\r\nHost: host.example\r\n\r\n"
        self.assertEqual(
            proxy._split_request_target("/a/b", req),
            ("host.example", 80, "/a/b"),
        )

    def test_origin_form_without_a_host_header_yields_no_host(self):
        host, _, _ = proxy._split_request_target("/a/b", b"GET /a/b HTTP/1.1\r\n\r\n")
        self.assertEqual(host, "")


def make_blob(order, layers):
    """A 1408-byte emblem body in the given byte order, for the endianness tests."""
    out = b""
    for i in range(render.NUM_LAYERS):
        if i < len(layers):
            shape, floats, outlined, flipped = layers[i]
        else:
            shape, floats, outlined, flipped = render.EMPTY_SHAPE, (0.0,) * 9, 0, 0
        out += (
            struct.pack(order + "H", shape) + b"\x00\x00"
            + struct.pack(order + "9f", *floats)
            + bytes([outlined, flipped]) + b"\x00\x00"
        )
    return out


SAMPLE_LAYERS = [
    (137, (1.0, 0.5, 0.25, 1.0, 0.1, -0.2, 0.0, 0.0, 90.0), 0, 0),
    (259, (0.0, 0.0, 1.0, 0.75, -0.3, 0.25, -1.0, -1.0, 180.0), 1, 1),
    (157, (0.2, 0.9, 0.1, 1.0, 0.0, 0.0, -2.0, -2.0, 0.0), 0, 1),
]


class TestEndianness(unittest.TestCase):
    """BO2 ran on the PS3's big-endian PowerPC and on little-endian x86 (PC and
    the PS4/PS5 ports). Assuming one of them mangles captures from the other."""

    def test_detects_little_endian(self):
        self.assertEqual(render.detect_endianness(make_blob("<", SAMPLE_LAYERS)), "<")

    def test_detects_big_endian(self):
        self.assertEqual(render.detect_endianness(make_blob(">", SAMPLE_LAYERS)), ">")

    def test_both_orders_parse_to_the_same_emblem(self):
        little = render.parse_slot_bytes(make_blob("<", SAMPLE_LAYERS))
        big = render.parse_slot_bytes(make_blob(">", SAMPLE_LAYERS))
        self.assertEqual(len(little), len(SAMPLE_LAYERS))
        self.assertEqual(len(big), len(little))
        for a, b in zip(little, big):
            self.assertEqual(a["shape"], b["shape"])
            self.assertAlmostEqual(a["r"], b["r"], places=5)
            self.assertAlmostEqual(a["rot"], b["rot"], places=3)
            self.assertEqual(a["flipped"], b["flipped"])

    def test_an_all_empty_blob_does_not_crash(self):
        self.assertEqual(render.parse_slot_bytes(make_blob("<", [])), [])

    def test_http_headers_are_stripped(self):
        blob = make_blob("<", SAMPLE_LAYERS)
        with_headers = b"HTTP/1.1 200 OK\r\nContent-Length: 1408\r\n\r\n" + blob
        self.assertEqual(len(render.parse_slot_bytes(with_headers)), len(SAMPLE_LAYERS))

    def test_explicit_order_overrides_detection(self):
        blob = make_blob(">", SAMPLE_LAYERS)
        self.assertNotEqual(
            render.parse_slot_bytes(blob, order="<"),
            render.parse_slot_bytes(blob, order=">"),
        )

    def test_render_survives_out_of_range_colours(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow not installed")
        layers = [(137, (1.02, -0.01, 0.5, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0, 0)]
        parsed = render.parse_slot_bytes(make_blob("<", layers))
        self.assertEqual(len(render.render_png(parsed, size=64).size), 2)


class TestGroupNameSafety(unittest.TestCase):
    """Group names arrive from control-panel URLs, and the panel listens on the
    LAN because the console has to reach it."""

    def test_generated_names_are_accepted(self):
        for name in ("001", "042", config.ACTIVE_NAME, "a-b_c"):
            self.assertTrue(storage.is_safe_group(name), name)

    def test_traversal_and_junk_are_rejected(self):
        for name in ("../../etc", "..", "a/b", "", None, "x" * 65, "a b", "a.b"):
            self.assertFalse(storage.is_safe_group(name), repr(name))

    def test_group_dir_refuses_to_build_an_escaping_path(self):
        with self.assertRaises(ValueError):
            storage.group_dir("../../etc")


class TestDataDirectory(unittest.TestCase):
    """A macOS .app writes to ~/Library/Application Support/..., which doesn't
    exist on first run - so importing has to create whatever it points at."""

    def test_a_missing_data_directory_is_created_on_import(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "does", "not", "exist", "yet")
            env = {**os.environ, "BO2_TOOLKIT_DATA_DIR": target}
            result = subprocess.run(
                [sys.executable, "-c",
                 "from emblemtool.state import write_state; write_state('CAPTURE')"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                env=env, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(os.path.join(target, "state.txt")))


class TestNetInfo(unittest.TestCase):
    def test_lan_ips_are_well_formed(self):
        entries = netinfo.get_lan_ips()
        self.assertIsInstance(entries, list)
        for entry in entries:
            self.assertEqual(set(entry), {"ip", "interface", "label", "primary"})
            self.assertFalse(entry["ip"].startswith("127."))
            self.assertFalse(entry["ip"].startswith("169.254."))
        self.assertLessEqual(sum(e["primary"] for e in entries), 1)

    def test_no_duplicate_addresses(self):
        ips = [e["ip"] for e in netinfo.get_lan_ips()]
        self.assertEqual(len(ips), len(set(ips)))


class TestControlPanelApi(unittest.TestCase):
    """End-to-end against a real server on a real socket."""

    @classmethod
    def setUpClass(cls):
        import threading
        cls.server = server.make_server(host="127.0.0.1", port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as r:
            return json.loads(r.read())

    def post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def test_status(self):
        body = self.get("/api/status")
        self.assertIn(body["mode"], ("off", "capture", "inject"))
        self.assertIn("detected", body)
        self.assertIn("proxy_error", body)

    def test_network_info_lists_addresses_and_consoles(self):
        body = self.get("/api/network-info")
        self.assertIsInstance(body["lan_ips"], list)
        self.assertEqual(body["proxy_port"], config.PROXY_PORT)
        self.assertTrue(body["console"]["name"])
        self.assertTrue(any(c["key"] == "ps4" for c in body["consoles"]))

    def test_console_can_be_changed_and_persists(self):
        try:
            self.post("/api/console", {"console": "ps4"})
            self.assertEqual(settings.get_console(), "ps4")
            self.assertEqual(self.get("/api/status")["console"], "ps4")
            self.post("/api/console", {"console": "not-a-console"})
            self.assertEqual(settings.get_console(), "auto")
        finally:
            settings.set_console("auto")

    def test_index_is_served(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/", timeout=10) as r:
            self.assertIn(b"BO2 Emblem Toolkit", r.read())

    def test_render_rejects_a_traversal_attempt(self):
        for path in (
            "/api/render/..%2f..%2f..%2fetc/0.png",
            "/api/render/foo/..%2f..%2fetc%2fpasswd.png",
        ):
            with self.subTest(path=path):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.get(path)
                self.assertEqual(caught.exception.code, 404)

    def test_static_traversal_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/../../config.py")
        self.assertEqual(caught.exception.code, 404)

    def test_select_rejects_an_unknown_group(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/select", {"group": "../../etc", "slot": 1})
        self.assertEqual(caught.exception.code, 404)

    def test_label_rejects_an_unknown_group(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/emblems/..%2f..%2fetc/1/label", {"label": "x"})
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
