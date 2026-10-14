# ADR 0006: Scope of Network Emulation and Serial Hardware Transport Testing

Status: accepted
Date: 2026-10-14
Card: P9-2
Author: chief-system-architect

## Context
Rule 3.3 of the autonomous commercial standard specifies network namespace and `tc netem` impairment testing (latency, packet loss, jitter) for applications that multiplex or tunnel network traffic across multiple physical interfaces. 

PenPress is a local-first desktop application and hardware pen plotter driver:
1. All core document composition, glyph synthesis, and G-code generation occur 100% offline on the local CPU without external network dependencies (Rule 7).
2. The UI communicates with the backend exclusively over loopback (`127.0.0.1`) or private Tailscale (`100.121.213.19`).
3. Hardware communication with the Ender 3 Pro occurs over a physical USB/UART serial connection (`/dev/ttyUSB0` or COM port) running Marlin line-numbered protocol (`N<line> <cmd>*<checksum>`).

We must establish the appropriate emulation model for PenPress transports: IP impairment vs. serial transmission fault injection.

## Options considered
| Option | Transport Tested | Relevant to PenPress? | Impairment Model | Overhead / Dependencies |
|---|---|---|---|---|
| A: Kernel `netns` + `tc netem` on IP loopback | TCP/IP HTTP REST API | Low (local loopback has 0 packet loss) | Packet loss, RTT jitter on `lo` | Requires root privileges, alters system network stack |
| B: Serial fault injection & line drop simulator | USB/UART serial driver (Marlin) | High (physical serial cables suffer noise, drops, buffer overflow) | Checksum corruptions, dropped `ok` ACKs, timeouts, `Resend: N` flow control | Pure Python simulator (`MarlinSerialDriver` loopback), zero root footprint |
| C: Dual-tier testing (Serial fault injection + HTTP load test) | Both Serial UART and HTTP daemon | High (covers both machine streaming and web studio telemetry) | Corrupted serial frames + rapid 2,000 req API pulsing | Verified via `test_serial_driver.py` and `scripts/load_test.py` |

## Decision
Adopt **Option C**. 
- USB serial transmission is tested using automated checksum corruption, dropped ACK injection, timeout detection, and atomic checkpoint recovery (implemented and verified in `src/penpress/machine/serial_driver.py` and `src/penpress/machine/recovery.py`).
- HTTP REST API is tested against high-frequency pulsing load (2,000 requests at >800 req/s with 0 file descriptor leaks and bounded memory in `scripts/load_test.py`).
- Synthetic Linux `tc netem` on local loopback is deemed not applicable because PenPress does not implement WAN routing, multipath TCP, or network bonding; running `tc netem` on loopback would introduce artificial jitter to local IPC without testing real plotter failure modes.

## Consequences
- USB serial noise, parity errors, and disconnects are comprehensively simulated and tested in unit and integration test suites.
- Loopback REST API is verified under load with zero descriptor leaks.
- Zero root permissions or destructive virtual ethernet configurations are required to run test suites.

## Fallback
If future plugins introduce remote telemetry sync over unreliable Wi-Fi or cellular networks, an opt-in network proxy test stand using `ip netns` and `tc netem` can be provisioned in an isolated container.
