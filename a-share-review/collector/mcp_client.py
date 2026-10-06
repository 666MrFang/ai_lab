"""Minimal MCP stdio JSON-RPC client for the Market MCP server.

This is the LIVE evidence source. It speaks the real MCP protocol
(``initialize`` -> ``tools/list`` -> ``tools/call``) to the server process; it
does not import the server module. Replay never uses this class.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

DEFAULT_PYTHON = r"D:\ai_lab\a-share-review\market-mcp\.venv\Scripts\python.exe"
DEFAULT_SERVER = r"D:\ai_lab\a-share-review\market-mcp\server.py"
DEFAULT_CWD = r"D:\ai_lab\a-share-review\market-mcp"


class McpStdioToolCaller:
    def __init__(
        self,
        python: str = DEFAULT_PYTHON,
        server: str = DEFAULT_SERVER,
        cwd: str = DEFAULT_CWD,
        data_mode: str = "real",
        timeout: float = 240.0,
    ):
        self._python = python
        self._server = server
        self._cwd = cwd
        self._data_mode = data_mode
        self._timeout = timeout
        self._proc: Optional[subprocess.Popen] = None
        self._queue: "queue.Queue" = queue.Queue()
        self._stderr: List[str] = []
        self._next_id = 100
        self.runtime_identity: Dict[str, Any] = {}
        self.tools: List[str] = []

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "McpStdioToolCaller":
        env = dict(os.environ)
        env["MARKET_DATA_MODE"] = self._data_mode
        env.pop("TUSHARE_TOKEN", None)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        self._proc = subprocess.Popen(
            [self._python, self._server], cwd=self._cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
        )
        threading.Thread(target=self._pump, args=(self._proc.stdout, "out"), daemon=True).start()
        threading.Thread(target=self._pump, args=(self._proc.stderr, "err"), daemon=True).start()
        self._handshake()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()

    # -- transport ---------------------------------------------------------
    def _pump(self, pipe, name: str) -> None:
        for line in iter(pipe.readline, ""):
            self._queue.put((name, line))
        self._queue.put((name, None))

    def _send(self, obj: Dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _wait(self, mid: int) -> Dict[str, Any]:
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            try:
                name, line = self._queue.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if name == "err":
                if line is not None:
                    self._stderr.append(line.rstrip())
                continue
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if msg.get("id") == mid:
                return msg
        raise TimeoutError("no response for id %s" % mid)

    def _handshake(self) -> None:
        self._send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "collector", "version": "1.0"}}})
        init = self._wait(1)
        info = init.get("result", {}).get("serverInfo", {})
        self.runtime_identity = {
            "build": info.get("version"),
            "name": info.get("name"),
            "provider": "akshare" if self._data_mode == "real" else "mock",
            "data_mode": self._data_mode,
        }
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = self._wait(2)
        self.tools = sorted(t["name"] for t in tools.get("result", {}).get("tools", []))

    @staticmethod
    def _parse(resp: Dict[str, Any]) -> Dict[str, Any]:
        result = resp.get("result", {}) or {}
        if result.get("structuredContent") is not None:
            return result["structuredContent"]
        for item in result.get("content", []) or []:
            if item.get("type") == "text":
                try:
                    return json.loads(item["text"])
                except Exception:
                    return {"success": False, "error_code": "UPSTREAM_SCHEMA_CHANGED",
                            "error": "unparseable tool text"}
        return {"success": False, "error_code": "INTERNAL_ERROR",
                "error": str(resp.get("error"))}

    def call(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self._next_id += 1
        mid = self._next_id
        self._send({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                    "params": {"name": tool, "arguments": arguments}})
        return self._parse(self._wait(mid))
