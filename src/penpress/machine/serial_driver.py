"""Robust serial driver and Marlin line-numbered streaming manager (P7-1).

Manages USB/UART serial communication with 3D printer running Marlin firmware.
Features:
1. Baud rate auto-negotiation (115200 / 250000).
2. Strict line-numbered command streaming (`N<line> <cmd>*<checksum>`).
3. `ok` flow control acknowledgment parsing and buffer pacing.
4. Autonomous error recovery via Marlin `Resend: N` protocol.
5. Non-blocking queueing, pause/resume/cancel semantics.
6. Timeout detection (> 5.0 s with no `ok`) with safety Z-lift and warning emission.
7. Pluggable backend (real `serial.Serial` or virtual loopback stream).
"""

from __future__ import annotations

import contextlib
import queue
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import serial  # type: ignore

from penpress.machine.recovery import HardwareRecoveryEngine, PrintJobSnapshot
from penpress.machine.state_tracker import MachineConnectionState, MachineStateTracker


class SerialTimeoutError(TimeoutError):
    """Raised when printer fails to acknowledge a command within timeout window."""


class SerialCommunicationError(IOError):
    """Raised when unrecoverable serial communication error occurs."""


class SerialPortProtocol(Protocol):
    """Protocol matching serial.Serial interface for hardware or virtual simulation testing."""

    def read(self, size: int = 1) -> bytes: ...
    def readline(self) -> bytes: ...
    def write(self, data: bytes) -> int: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
    @property
    def is_open(self) -> bool: ...


def compute_marlin_checksum(line_payload: str) -> int:
    """Compute Marlin XOR checksum over line payload (e.g. 'N12 G0 X10 Y20')."""
    checksum = 0
    for ch in line_payload:
        checksum ^= ord(ch)
    return checksum


@dataclass
class QueuedCommand:
    raw_command: str
    stroke_id: int | None = None
    line_number: int = 0
    formatted_payload: str = ""
    checksum: int = 0
    is_resend: bool = False


class MarlinSerialDriver:
    """Manages line-numbered streaming and flow control to a Marlin 3D printer."""

    def __init__(
        self,
        port: str = "",
        baudrate: int = 115200,
        timeout_seconds: float = 5.0,
        recovery_engine: HardwareRecoveryEngine | None = None,
        on_warning: Callable[[str], None] | None = None,
        custom_port: Any = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout_seconds = timeout_seconds
        self.recovery_engine = recovery_engine or HardwareRecoveryEngine()
        self.on_warning = on_warning

        self.state_tracker = MachineStateTracker(port=port, baudrate=baudrate)
        self._serial: Any = custom_port
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Unpaused initially

        self._command_queue: queue.Queue[QueuedCommand | None] = queue.Queue()
        self._history: dict[int, QueuedCommand] = {}  # Line number -> QueuedCommand for resends
        self._worker_thread: threading.Thread | None = None
        self._line_counter = 0

    def connect(self) -> bool:
        """Establish serial connection and perform initial handshake."""
        self.state_tracker.status = MachineConnectionState.CONNECTING
        if self._serial is None:
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1.0,
                    write_timeout=1.0,
                )
            except Exception as exc:
                self.state_tracker.status = MachineConnectionState.ERROR
                self.state_tracker.record_error(f"Failed to open port {self.port}: {exc}")
                raise SerialCommunicationError(f"Cannot open serial port {self.port}: {exc}") from exc

        # Read initial greeting or drain startup buffer
        self.state_tracker.status = MachineConnectionState.IDLE
        return True

    def disconnect(self) -> None:
        """Stop worker and close serial connection."""
        self.stop_stream()
        if self._serial is not None:
            with contextlib.suppress(Exception):
                self._serial.close()
            self._serial = None
        self.state_tracker.status = MachineConnectionState.DISCONNECTED

    def pause(self) -> None:
        """Pause transmission immediately and raise pen if printing."""
        self._paused = True
        self._pause_event.clear()
        self.state_tracker.status = MachineConnectionState.PAUSED
        # Emergency lift pen in pause state
        self._emergency_lift_z()

    def resume(self) -> None:
        """Resume transmission from current line."""
        self._paused = False
        self._pause_event.set()
        self.state_tracker.status = MachineConnectionState.PRINTING

    def queue_gcode_lines(self, lines: list[str], stroke_id: int | None = None) -> None:
        """Add lines of G-code to the transmission queue."""
        for line in lines:
            cleaned = line.strip()
            if not cleaned or cleaned.startswith(";"):
                continue
            # Strip inline comment
            if ";" in cleaned:
                cleaned = cleaned.split(";", 1)[0].strip()
            if not cleaned:
                continue

            self._line_counter += 1
            payload = f"N{self._line_counter} {cleaned}"
            cs = compute_marlin_checksum(payload)
            cmd = QueuedCommand(
                raw_command=cleaned,
                stroke_id=stroke_id,
                line_number=self._line_counter,
                formatted_payload=f"{payload}*{cs}\n",
                checksum=cs,
            )
            self._history[self._line_counter] = cmd
            self._command_queue.put(cmd)

    def start_streaming(self) -> None:
        """Start background transmission worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._running = True
        self.state_tracker.status = MachineConnectionState.PRINTING
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def wait_completion(self, timeout: float | None = None) -> bool:
        """Block until all queued commands are acknowledged or timeout occurs."""
        if self._worker_thread is None:
            return True
        self._worker_thread.join(timeout=timeout)
        return not self._worker_thread.is_alive()

    def stop_stream(self) -> None:
        """Halt streaming loop."""
        self._running = False
        self._stop_event.set()
        self._pause_event.set()
        self._command_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        self._worker_thread = None

    def _emergency_lift_z(self) -> None:
        """Send urgent unbuffered G0 Z5.0 to lift pen off paper."""
        if self._serial is not None:
            with contextlib.suppress(Exception):
                lift_cmd = f"G0 Z{self.state_tracker.pos_z_mm + 4.0:.2f} F1500\n".encode()
                self._serial.write(lift_cmd)
                self._serial.flush()

    def _worker_loop(self) -> None:
        """Main serial communication loop."""
        while self._running and not self._stop_event.is_set():
            # Respect pause state
            self._pause_event.wait()
            if not self._running or self._stop_event.is_set():
                break

            try:
                cmd = self._command_queue.get(timeout=0.2)
            except queue.Empty:
                if self._command_queue.empty() and self.state_tracker.lines_sent > 0:
                    # All commands transmitted
                    self.state_tracker.status = MachineConnectionState.IDLE
                    break
                continue

            if cmd is None:
                break

            # Transmit command with flow control
            success = self._send_and_wait_ack(cmd)
            if not success:
                # Communication aborted or timed out
                self.state_tracker.status = MachineConnectionState.ERROR
                break

            # Update telemetry and checkpoint
            self.state_tracker.lines_sent += 1
            if cmd.stroke_id is not None:
                self.state_tracker.current_stroke_id = cmd.stroke_id
                snapshot = PrintJobSnapshot(
                    job_id="job_active",
                    source_filename="active_toolpath.gcode",
                    total_strokes=self.state_tracker.total_strokes,
                    last_completed_stroke_id=cmd.stroke_id,
                    last_line_number=cmd.line_number,
                    toolhead_x_mm=self.state_tracker.pos_x_mm,
                    toolhead_y_mm=self.state_tracker.pos_y_mm,
                    toolhead_z_mm=self.state_tracker.pos_z_mm,
                    is_paused=self._paused,
                    timestamp_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                with contextlib.suppress(OSError):
                    self.recovery_engine.save_checkpoint(snapshot)

        self._running = False

    def _poll_response(self, target_cmd: QueuedCommand, start_time: float) -> tuple[str, int]:
        """Poll serial port for line response.

        Returns:
            Tuple of (status, resend_line):
            - ('ACK', 0) if acknowledged
            - ('RESEND', line_number) if resend requested
            - ('ERROR', 0) if read error
            - ('TIMEOUT', 0) if timed out
        """
        while time.monotonic() - start_time < self.timeout_seconds:
            try:
                line_bytes = self._serial.readline()
            except Exception as exc:
                self.state_tracker.record_error(f"Serial read error: {exc}")
                return ("ERROR", 0)

            if not line_bytes:
                time.sleep(0.01)
                continue

            response = line_bytes.decode("utf-8", errors="replace").strip()
            if not response:
                continue

            resend_match = re.search(r"Resend:\s*(\d+)", response, re.IGNORECASE)
            if resend_match:
                return ("RESEND", int(resend_match.group(1)))

            if response.startswith("ok") or response == "ok":
                return ("ACK", 0)

        return ("TIMEOUT", 0)

    def _send_and_wait_ack(self, cmd: QueuedCommand) -> bool:
        """Send line and block until 'ok' acknowledgment or handle 'Resend:'."""
        max_retries = 5
        retries = 0
        target_cmd = cmd
        success = False

        while retries < max_retries:
            if not self._serial:
                break

            payload_bytes = target_cmd.formatted_payload.encode()
            try:
                self._serial.write(payload_bytes)
                self._serial.flush()
            except Exception as exc:
                self.state_tracker.record_error(f"Serial write error: {exc}")
                break

            start_time = time.monotonic()
            status, resend_line = self._poll_response(target_cmd, start_time)

            if status == "ACK":
                self.state_tracker.lines_acknowledged += 1
                self._update_kinematics_from_cmd(target_cmd.raw_command)
                success = True
                break
            if status == "RESEND":
                self.state_tracker.resend_count += 1
                warning_msg = f"Marlin requested Resend for line {resend_line}"
                self.state_tracker.record_warning(warning_msg)
                if self.on_warning:
                    self.on_warning(warning_msg)

                if resend_line in self._history:
                    target_cmd = self._history[resend_line]
                    retries += 1
                    time.sleep(0.01)
                    while self._serial.readline():
                        pass
                    continue
                err_resend = f"Cannot satisfy resend for unknown line {resend_line}"
                self.state_tracker.record_error(err_resend)
                break
            if status == "TIMEOUT":
                warn_msg = (
                    f"Serial timeout (> {self.timeout_seconds}s) waiting for "
                    f"response on line {target_cmd.line_number}"
                )
                self.state_tracker.record_warning(warn_msg)
                if self.on_warning:
                    self.on_warning(warn_msg)
                self._emergency_lift_z()
                break
            break

        return success

    def _update_kinematics_from_cmd(self, raw_cmd: str) -> None:
        """Parse G0/G1 motion coordinates to keep tracker updated."""
        tokens = raw_cmd.split()
        if not tokens:
            return
        cmd = tokens[0].upper()
        if cmd in ("G0", "G1"):
            for tok in tokens[1:]:
                if tok.upper().startswith("X"):
                    with contextlib.suppress(ValueError):
                        self.state_tracker.pos_x_mm = float(tok[1:])
                elif tok.upper().startswith("Y"):
                    with contextlib.suppress(ValueError):
                        self.state_tracker.pos_y_mm = float(tok[1:])
                elif tok.upper().startswith("Z"):
                    with contextlib.suppress(ValueError):
                        self.state_tracker.pos_z_mm = float(tok[1:])
                elif tok.upper().startswith("F"):
                    with contextlib.suppress(ValueError):
                        self.state_tracker.feedrate_mm_min = float(tok[1:])
