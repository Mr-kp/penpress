# Hardware Test & Calibration Protocol for Ender 3 Pro Pen Plotter

This document describes the manual step-by-step calibration procedure to measure physical machine limits, Z contact heights, spring flexure, bed clip clearances, and backlash.

---

## Safety Pre-Checks
1. **Zero Heat Enforcement**: Disconnect or ensure hotend heater (`E0`) and heated bed are set to 0 °C (`M104 S0`, `M140 S0`).
2. **Spring-Loaded Pen Mount**: Always use a compliant spring-loaded pen toolhead mount with $\ge 2.0$ mm of axial travel. Never fix a rigid pen directly to the metal extruder carriage without a spring.
3. **Emergency Stop**: Keep your hand near the power switch during the first homing pass (`G28`).

---

## Step 1: Toolhead XY Offset and Clip Keepout Measurement
1. Mount the pen in the spring-loaded holder.
2. Home all axes: `G28`.
3. Read nozzle coordinate: `M114`.
4. Manually jog the pen tip over the front-left corner of the PEI bed:
   - Record $(X_0, Y_0)$ in millimetres.
   - Toolhead offset = $(X_0 - 0.0, Y_0 - 0.0)$.
5. Identify binder clips holding the PEI sheet:
   - Front clips: Measure intrusion into bed ($Y_{\text{clip}}$ typically $8.0$ to $12.0$ mm).
   - Back clips: Measure intrusion ($235.0 - Y_{\text{clip}}$).
   - Safe usable margin defaults: `10.0 mm` on all 4 sides.

---

## Step 2: Z-Touch Paper Contact Calibration
1. Tape a scrap sheet of paper (80 gsm) to the centre of the bed.
2. Jog $X$ and $Y$ to bed center: `G0 X117.5 Y117.5 Z10.0 F3000`.
3. Lower $Z$ slowly in 0.2 mm increments until the pen tip first touches the paper:
   - Note the height: $Z_{\text{touch}}$.
4. Lower $Z$ by an additional $0.4$ mm to pre-load the compliance spring:
   - $Z_{\text{write}} = Z_{\text{touch}} - 0.4 \text{ mm}$.
5. Safe travel clearance:
   - $Z_{\text{lift}} = Z_{\text{touch}} + 3.0 \text{ mm}$.
6. Hardware safety floor:
   - $Z_{\text{write\_min}} = Z_{\text{touch}} - 1.0 \text{ mm}$ (prevents mechanical bottom-out and bed gouging).

---

## Step 3: Motion Speed and Junction Deviation Stress Test
1. Run the test pattern G-code (`penpress render-text tests/fixtures/p1_5_text_120words.txt`).
2. Evaluate writing quality at different feedrates:
   - $1200 \text{ mm/min}$ ($20 \text{ mm/s}$): Ultra-high crispness, zero ink skipping.
   - $2400 \text{ mm/min}$ ($40 \text{ mm/s}$): Nominal high-speed academic writing.
   - $3600 \text{ mm/min}$ ($60 \text{ mm/s}$): Maximum recommended speed before centrifugal rollerball ink thinning.

---

## Step 4: Paper Fit and A4 Two-Pass Error Budget
- **Ender 3 Pro Usable Bed**: $235 \times 235$ mm. Safe usable printable envelope: $215 \times 215$ mm.
- **A5 Paper ($148 \times 210$ mm)**: Fits completely in a single pass with comfortable $15$ mm margins.
- **A4 Paper ($210 \times 297$ mm)**: Length ($297$ mm) exceeds physical Y travel ($235$ mm).
  * Requires shifting the paper manually between Page Half 1 and Page Half 2.
  * Mechanical repositioning repeatability: Human alignment with physical jig pins yields $\pm 0.5$ mm to $\pm 1.2$ mm error, exceeding our $\le 0.25$ mm inter-line tolerance.
  * **Architectural Decision**: A4 two-pass is marked *unsupported in v0.1*. A5 and custom folded booklets are supported natively.

---

## Results Recording
Save measured values to `~/.penpress/hardware-results.json`:
```json
{
  "schema_version": "1.0",
  "timestamp": "2026-10-13T12:00:00Z",
  "machine_name": "Ender 3 Pro (Pen Plotter)",
  "bed_usable_width_mm": 215.0,
  "bed_usable_height_mm": 215.0,
  "measured_clip_keepouts": {
    "left_mm": 10.0,
    "right_mm": 10.0,
    "bottom_mm": 10.0,
    "top_mm": 10.0
  },
  "z_contact_nominal_mm": 0.5,
  "z_contact_safe_floor_mm": 0.1,
  "z_lift_clearance_mm": 3.5,
  "max_reliable_xy_feedrate_mm_min": 2400.0,
  "max_reliable_z_feedrate_mm_min": 1200.0,
  "pen_mount_backlash_x_mm": 0.08,
  "pen_mount_backlash_y_mm": 0.08,
  "paper_fit_modes": ["A5_single_pass", "A4_two_pass_unsupported"]
}
```
