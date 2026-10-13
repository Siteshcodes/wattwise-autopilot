import os
import socket
import subprocess
import sys
import time

import httpx
import pytest


@pytest.fixture
def server(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "WATTWISE_DB": str(tmp_path / "test.sqlite3"), "WATTWISE_MCP_PORT": str(port), "WATTWISE_DEMO_NOW": "2026-10-12T20:00:00+05:30"}
    log = (tmp_path / "server.log").open("w+")
    proc = subprocess.Popen([sys.executable, "-m", "wattwise.server"], env=env, stdout=log, stderr=log)
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(150):
            if proc.poll() is not None:
                log.seek(0)
                pytest.fail(log.read())
            try:
                httpx.get(url, timeout=.3)
                break
            except httpx.TransportError:
                time.sleep(.1)
        else:
            pytest.fail("MCP server did not start")
        yield url, env["WATTWISE_DB"]
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()
