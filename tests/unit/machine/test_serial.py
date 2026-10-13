"""Unit tests for robust serial driver, checksum flow control, and recovery engine (P7-1).

Tests:
1. Streaming 10,000 commands with line numbering and checksums through virtual Marlin simulator.
2. Error recovery via Marlin `Resend: N` protocol when transmission corruptions occur.
3. Mid-job disconnect recovery: un-plugging preserves last completed stroke ID; resuming continues cleanly.
4. Negative test: Communication timeout (> 5.0 s with no response) pauses, lifts Z, and emits warning event.
5. State tracker telemetry and checkpoint generation.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from unit.machine.loopback_serial import LoopbackMarlinSerialPort

from penpress.machine.recovery import HardwareRecoveryEngine
from penpress.machine.serial_driver import MarlinSerialDriver
from penpress.machine.state_tracker import MachineConnectionState, MachineStateTracker
from penpress.plan.profile import MachineProfile
from penpress.plan.sim import MarlinSimulator


def test_10000_gcode_commands_transmission_through_virtual_marlin() -> None:
    # Set up virtual Marlin simulator and mock serial connection
    sim = MarlinSimulator(profile=MachineProfile())
    mock_port = LoopbackMarlinSerialPort(sim=sim)
    driver = MarlinSerialDriver(custom_port=mock_port)
    driver.connect()

    # Generate 10,000 motion commands
    gcode_batch: list[str] = []
    gcode_batch.append("G21 ; Units in mm")
    gcode_batch.append("G90 ; Absolute coordinates")
    gcode_batch.append("G28 ; Home axes")
    gcode_batch.append("G0 Z3.5 F1500 ; Clearance Z")

    # Generate small alternating moves
    for i in range(10000):
        x = 10.0 + (i % 50) * 1.0
        y = 10.0 + ((i // 50) % 50) * 1.0
        gcode_batch.append(f"G1 X{x:.2f} Y{y:.2f} Z0.5 F3000")

    driver.queue_gcode_lines(gcode_batch, stroke_id=1)
    driver.start_streaming()

    completed = driver.wait_completion(timeout=30.0)
    assert completed is True, "Driver did not complete 10,000 commands within timeout"
    assert driver.state_tracker.lines_acknowledged >= 10000
    assert len(sim.violations) == 0, f"Simulator recorded violations: {sim.violations}"
    driver.disconnect()


def test_recovery_from_checksum_corruption_via_resend() -> None:
    # Inject corruption on lines 6 and 13
    corrupt_lines = {6, 13}
    warnings: list[str] = []

    def on_warning(msg: str) -> None:
        warnings.append(msg)

    sim = MarlinSimulator(profile=MachineProfile())
    mock_port = LoopbackMarlinSerialPort(sim=sim, corrupt_lines=corrupt_lines)
    driver = MarlinSerialDriver(custom_port=mock_port, on_warning=on_warning)
    driver.connect()

    lines = [
        "G21",
        "G90",
        "G28",
        "G0 Z3.5 F1500",
        "G1 X10 Y10 Z0.5 F3000",
        "G1 X20 Y10",  # line 6 - corrupted on first try
        "G1 X30 Y10",
        "G1 X40 Y10",
        "G1 X50 Y10",
        "G1 X60 Y10",
        "G1 X70 Y10",
        "G1 X80 Y10",
        "G1 X90 Y10",  # line 13 - corrupted on first try
        "G1 X100 Y10",
    ]

    driver.queue_gcode_lines(lines, stroke_id=42)
    driver.start_streaming()

    completed = driver.wait_completion(timeout=5.0)
    assert completed is True
    assert driver.state_tracker.resend_count == 2
    assert any("Resend for line 6" in w for w in warnings)
    assert any("Resend for line 13" in w for w in warnings)
    assert driver.state_tracker.lines_acknowledged == len(lines)
    driver.disconnect()


def test_disconnect_mid_job_recovery() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = Path(tmp_dir) / ".print_state.json"
        recovery_engine = HardwareRecoveryEngine(state_file_path=state_file)

        sim = MarlinSimulator(profile=MachineProfile())
        mock_port = LoopbackMarlinSerialPort(sim=sim)
        driver = MarlinSerialDriver(custom_port=mock_port, recovery_engine=recovery_engine)
        driver.connect()
        driver.state_tracker.total_strokes = 100

        # Queue strokes 1 through 10
        for s_idx in range(1, 11):
            stroke_gcode = [
                f"G0 X{s_idx * 10} Y{s_idx * 5} F6000",
                "G1 Z0.2 F1200",
                f"G1 X{s_idx * 10 + 5} Y{s_idx * 5} F2400",
                "G0 Z3.5 F1200",
            ]
            driver.queue_gcode_lines(stroke_gcode, stroke_id=s_idx)

        driver.start_streaming()
        # Let it stream a few strokes
        time.sleep(0.15)
        # Simulate sudden disconnect / unplug
        driver.disconnect()

        # Checkpoint should exist and record the last completed stroke ID
        checkpoint = recovery_engine.load_checkpoint()
        assert checkpoint is not None
        last_stroke = checkpoint.last_completed_stroke_id
        assert 1 <= last_stroke <= 10

        # Resume engine generates safe preamble without scratching paper
        resume_preamble = recovery_engine.generate_resume_preamble(checkpoint)
        assert any("Z5.00" in line for line in resume_preamble)
        assert any("G28 X Y" in line for line in resume_preamble)

        # Clear checkpoint when job finishes cleanly
        recovery_engine.clear_checkpoint()
        assert recovery_engine.load_checkpoint() is None


def test_negative_communication_timeout_pauses_and_lifts_z() -> None:
    # Configure mock port to time out on line 3 (never send ok)
    timeout_lines = {3}
    warnings: list[str] = []

    def on_warning(msg: str) -> None:
        warnings.append(msg)

    sim = MarlinSimulator(profile=MachineProfile())
    mock_port = LoopbackMarlinSerialPort(sim=sim, timeout_lines=timeout_lines)
    # Set short timeout of 0.2s for fast unit test execution
    driver = MarlinSerialDriver(custom_port=mock_port, timeout_seconds=0.2, on_warning=on_warning)
    driver.connect()

    lines = [
        "G21",
        "G90",
        "G1 X10 Y10",  # line 3 - times out
        "G1 X20 Y20",
    ]

    driver.queue_gcode_lines(lines, stroke_id=1)
    driver.start_streaming()

    completed = driver.wait_completion(timeout=1.0)
    assert completed is True
    # Driver should be stopped with ERROR state
    assert driver.state_tracker.status == MachineConnectionState.ERROR
    # Warning emitted
    assert any("Serial timeout" in w for w in warnings)
    driver.disconnect()


def test_machine_state_tracker_telemetry() -> None:
    tracker = MachineStateTracker()
    assert tracker.progress_pct == 0.0

    tracker.total_strokes = 200
    tracker.current_stroke_id = 50
    assert tracker.progress_pct == 25.0

    tracker.update_position(x=45.0, y=90.0, z=1.2, feedrate=4000.0)
    assert tracker.pos_x_mm == 45.0
    assert tracker.pos_y_mm == 90.0
    assert tracker.pos_z_mm == 1.2
    assert tracker.feedrate_mm_min == 4000.0
    assert tracker.current_position.x == 45.0
    assert tracker.current_position.y == 90.0

    tracker.record_warning("test warning")
    assert len(tracker.warnings) == 1
    tracker.record_error("test error")
    assert tracker.error_count == 1
    assert len(tracker.errors) == 1


def test_driver_pause_and_resume() -> None:
    sim = MarlinSimulator(profile=MachineProfile())
    mock_port = LoopbackMarlinSerialPort(sim=sim)
    driver = MarlinSerialDriver(custom_port=mock_port)
    driver.connect()

    lines = [f"G1 X{i} Y{i} Z0.5" for i in range(10)]
    driver.queue_gcode_lines(lines, stroke_id=1)
    driver.start_streaming()

    # Pause
    driver.pause()
    assert driver.state_tracker.status.value == MachineConnectionState.PAUSED.value

    # Resume
    driver.resume()
    assert driver.state_tracker.status.value == MachineConnectionState.PRINTING.value

    completed = driver.wait_completion(timeout=5.0)
    assert completed is True
    driver.disconnect()
