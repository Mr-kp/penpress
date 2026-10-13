// PenPress Studio Frontend Controller
// Implements view switching, canvas drawing, bed rendering, and toolpath animation

document.addEventListener("DOMContentLoaded", () => {
  // 1. Navigation switching
  const navItems = document.querySelectorAll(".nav-item");
  const views = document.querySelectorAll(".workspace-view");

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      navItems.forEach((n) => n.classList.remove("active"));
      views.forEach((v) => v.classList.remove("active"));

      btn.classList.add("active");
      const targetViewId = btn.getAttribute("data-view");
      const targetView = document.getElementById(targetViewId);
      if (targetView) {
        targetView.classList.add("active");
      }
    });
  });

  // 2. Handwriting Canvas Setup
  const hwCanvas = document.getElementById("handwriting-canvas");
  if (hwCanvas && hwCanvas.getContext) {
    const ctx = hwCanvas.getContext("2d");
    if (ctx) {
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.lineJoin = "round";

      // Draw sample handwritten glyph 'a'
      ctx.beginPath();
      ctx.arc(300, 200, 45, 0, Math.PI * 2);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(345, 155);
      ctx.lineTo(345, 245);
      ctx.stroke();
    }
  }

  // 3. Bed Alignment View Setup
  const bedCanvas = document.getElementById("bed-canvas");
  if (bedCanvas && bedCanvas.getContext) {
    const ctx = bedCanvas.getContext("2d");
    if (ctx) {
      // Draw Ender 3 bed boundary (235x235 mm)
      ctx.fillStyle = "#12141a";
      ctx.fillRect(50, 50, 400, 400);
      ctx.strokeStyle = "#2d3348";
      ctx.lineWidth = 2;
      ctx.strokeRect(50, 50, 400, 400);

      // Draw paper sheet (A5 ~ 148 x 210 mm)
      ctx.fillStyle = "#fcfbf9";
      ctx.fillRect(125, 75, 250, 350);

      // Draw metallic binder clips with expanded keepout
      // Front clips
      ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
      ctx.fillRect(85, 40, 50, 30);
      ctx.fillRect(365, 40, 50, 30);
      ctx.strokeStyle = "#ef4444";
      ctx.strokeRect(85, 40, 50, 30);
      ctx.strokeRect(365, 40, 50, 30);
    }
  }

  // 4. Live Toolpath Visualizer
  const tpCanvas = document.getElementById("toolpath-canvas");
  if (tpCanvas && tpCanvas.getContext) {
    const ctx = tpCanvas.getContext("2d");
    if (ctx) {
      // Draw simulated toolpaths
      ctx.fillStyle = "#090a0d";
      ctx.fillRect(0, 0, 600, 450);

      // Draw light ruled lines
      ctx.strokeStyle = "#161924";
      ctx.lineWidth = 1;
      for (let y = 50; y < 400; y += 30) {
        ctx.beginPath();
        ctx.moveTo(50, y);
        ctx.lineTo(550, y);
        ctx.stroke();
      }

      // Draw animated strokes
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let x = 60; x < 500; x += 15) {
        const y = 140 + Math.sin(x * 0.08) * 12;
        if (x === 60) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Toolhead position indicator
      ctx.fillStyle = "#f43f5e";
      ctx.beginPath();
      ctx.arc(380, 140, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
});
