; --- PenPress Marlin G-code Output ---
; Machine: Test Plotter
; Page: 148.0 x 210.0 mm
M104 S0 ; Extruder heater off
M140 S0 ; Bed heater off
M107 ; Fan off
G21 ; Units in millimetres
G90 ; Absolute coordinates
G0 Z3.00 F1200 ; Safe Z lift
G28 ; Home axes
G0 Z3.00 F1200 ; Restore clearance Z
; Total strokes: 1, total segments: 1
G0 X25.000 Y25.000 F6000 ; Move to stroke 1 start
G1 Z0.50 F800 ; Pen down
G1 X65.000 Y25.000 F2400
G0 Z3.00 F1200 ; Pen up
; --- End of Print ---
G0 Z13.00 F1200 ; Final park lift
G0 X10.0 Y210.0 F6000 ; Present paper
M84 ; Disable steppers
