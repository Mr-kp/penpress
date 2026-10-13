"""Loopback serial port implementing SerialPortProtocol for Marlin testing."""

from __future__ import annotations

import queue
import re

from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator


class LoopbackMarlinSerialPort:
    """Simulates a bidirectional hardware serial port connected to MarlinSimulator."""

    def __init__(
        self,
        sim: MarlinSimulator | None = None,
        corrupt_lines: set[int] | None = None,
        timeout_lines: set[int] | None = None,
    ) -> None:
        self.sim = sim or MarlinSimulator(profile=MachineProfile())
        self.corrupt_lines = corrupt_lines or set()
        self.timeout_lines = timeout_lines or set()
        self._write_buffer = bytearray()
        self._rx_queue: queue.Queue[bytes] = queue.Queue()
        self._open = True
        self.lines_received: list[str] = []

    @property
    def is_open(self) -> bool:
        return self._open

    def close(self) -> None:
        self._open = False

    def write(self, data: bytes) -> int:
        self._write_buffer.extend(data)
        while b"\n" in self._write_buffer:
            idx = self._write_buffer.index(b"\n")
            line_bytes = bytes(self._write_buffer[: idx + 1])
            del self._write_buffer[: idx + 1]
            self._process_incoming_line(line_bytes)
        return len(data)

    def _process_incoming_line(self, line_bytes: bytes) -> None:
        line_str = line_bytes.decode("utf-8", errors="replace").strip()
        if not line_str:
            return

        self.lines_received.append(line_str)

        m = re.match(r"^N(\d+)\s+", line_str)
        line_num = int(m.group(1)) if m else -1

        # Simulate timeout (no response)
        if line_num in self.timeout_lines:
            return

        # Simulate transmission corruption
        if line_num in self.corrupt_lines:
            # Corrupt the line by modifying checksum or content
            resp = f"Error:checksum mismatch, Last Line: {line_num - 1}\nResend: {line_num}\nok\n"
            self.corrupt_lines.remove(line_num)  # corrupt only on first try
            for r_line in resp.strip().split("\n"):
                self._rx_queue.put((r_line + "\n").encode("utf-8"))
            return

        # Normal execution through Marlin simulator
        sim_resp = self.sim.execute_line(line_str)
        for r_line in sim_resp.strip().split("\n"):
            self._rx_queue.put((r_line + "\n").encode("utf-8"))

    def readline(self) -> bytes:
        try:
            return self._rx_queue.get(timeout=0.05)
        except queue.Empty:
            return b""

    def read(self, size: int = 1) -> bytes:
        return self.readline()

    def flush(self) -> None:
        pass
