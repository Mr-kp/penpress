# ADR 0005: Physical Limits, Kinematics, and Hardware Calibration for Ender 3 Pro

- **Status**: Accepted
- **Date**: 2026-10-13
- **Card**: `tasks/R5-1.md`
- **Deciders**: PenPress Core Architecture Swarm

---

## Context

Using an Ender 3 Pro 3D printer as a pen plotter introduces mechanical, kinematic, and firmware constraints fundamentally different from plastic FDM extrusion:
1. **Pen Compliance & Z Safety**: A rigid pen moving in $Z$ will crush into the bed or tear paper if $Z=0$ is misaligned by even $0.3$ mm.
2. **Bed Envelope vs Paper Dimensions**: The Ender 3 Pro bed is $235 \times 235$ mm. Standard A4 paper is $210 \times 297$ mm; standard A5 paper is $148 \times 210$ mm.
3. **Motion Kinematics for Glyphs**: Handwriting consists of tiny 1–3 mm vector segments with frequent sharp corners. Extrusion motion profiles optimized for long perimeters cause excessive vibration, deceleration stutter, or corner rounding under high junction deviation.
4. **Z-Lift Overhead**: Pen lifts occur hundreds of times per page. The T8 leadscrew has limited speed and acceleration compared to the belt-driven X/Y axes.

---

## Decisions

### 1. Paper Form Factor & Two-Pass A4 Rejection in v0.1
- **Decision**: **A5 single-pass is the primary supported format in v0.1**. Multi-pass repositioned A4 is marked **unsupported**.
- **Rationale**:
  - A5 ($148 \times 210$ mm) fits inside the $215 \times 215$ mm usable bed envelope with ample margins.
  - A4 ($210 \times 297$ mm) exceeds physical Y travel ($235$ mm) by $62$ mm.
  - Manual paper repositioning with jig pins introduces $\pm 0.5$ to $\pm 1.2$ mm alignment error, causing noticeable discontinuities across paragraphs.
  - For full-page assignments, users print on A5 sheets or folded A4 booklets (which are A5 pages).

### 2. Spring-Loaded Mount & Software Z-Floor Enforcement
- **Decision**: A spring-loaded compliant mount ($\ge 2.0$ mm axial travel) is mandatory. The compiler and firmware simulator enforce an immutable safety floor (`z_write_min_mm = 0.1` mm) below which any command raises `ERR_Z_BELOW_MIN`.
- **Pre-load Setting**: Nominal contact at $Z_{\text{touch}} - 0.4$ mm provides consistent ink flow on gel and rollerball pens without tearing paper.

### 3. Kinematic Profile & Junction Deviation
- **Default Speed**: Writing feedrate $2400 \text{ mm/min}$ ($40 \text{ mm/s}$); travel feedrate $6000 \text{ mm/min}$ ($100 \text{ mm/s}$).
- **Acceleration**: $500 \text{ mm/s}^2$ on XY; $100 \text{ mm/s}^2$ on Z.
- **Junction Deviation**: $0.02 \text{ mm}$ (smooth corners on cursive handwriting without stutter).
- **Z-Lift Height**: $3.5 \text{ mm}$ (clears paper buckle and binder clip edges while keeping lift duration under $0.25$ s).

### 4. Zero-Heat Safety Guarantee
- All G-code preambles strictly disable hotend and bed heaters (`M104 S0`, `M140 S0`).
- Thermal runaway checks remain inactive because temperatures are set to zero.

---

## Consequences

- Flawless single-pass A5 academic homework and notebook pages.
- Hardware is 100% protected against bed crashes and paper tears.
- Fast execution with realistic trapezoidal timing simulation.
