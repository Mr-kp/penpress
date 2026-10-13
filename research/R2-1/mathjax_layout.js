// Bridge script: convert LaTeX math string into a structured layout tree of glyphs and rules.
// Runs using Node.js and MathJax-full liteAdaptor.

const mathjax = require('./vendor/node_modules/mathjax-full/js/mathjax.js').mathjax;
const TeX = require('./vendor/node_modules/mathjax-full/js/input/tex.js').TeX;
const SVG = require('./vendor/node_modules/mathjax-full/js/output/svg.js').SVG;
const adaptor = require('./vendor/node_modules/mathjax-full/js/adaptors/liteAdaptor.js').liteAdaptor;
const RegisterHTMLHandler = require('./vendor/node_modules/mathjax-full/js/handlers/html.js').RegisterHTMLHandler;

const htmlAdaptor = adaptor();
RegisterHTMLHandler(htmlAdaptor);

const AllPackages = require('./vendor/node_modules/mathjax-full/js/input/tex/AllPackages.js').AllPackages;
const texPackages = AllPackages.filter(p => !['noerrors', 'noundefined'].includes(p));

const tex = new TeX({
  packages: texPackages
});
const svg = new SVG({fontCache: 'none'});
const doc = mathjax.document('', {InputJax: tex, OutputJax: svg});

function extractElements(mathNode) {
  const elements = [];

  function recurse(node, curX, curY, scaleX, scaleY) {
    if (!node || !node.kind || node.kind === '#text' || !node.attributes) return;
    let nextX = curX;
    let nextY = curY;
    let nextScaleX = scaleX;
    let nextScaleY = scaleY;

    const transform = htmlAdaptor.getAttribute(node, 'transform');
    if (transform) {
      // Parse translate
      const transMatch = /translate\(([-0-9.]+)[,\s]+([-0-9.]+)\)/.exec(transform);
      if (transMatch) {
        nextX += parseFloat(transMatch[1]) * scaleX;
        nextY += parseFloat(transMatch[2]) * scaleY;
      }
      // Parse scale
      const scaleMatch = /scale\(([-0-9.]+)(?:[,\s]+([-0-9.]+))?\)/.exec(transform);
      if (scaleMatch) {
        const sx = parseFloat(scaleMatch[1]);
        const sy = scaleMatch[2] ? parseFloat(scaleMatch[2]) : sx;
        nextScaleX *= sx;
        nextScaleY *= sy;
      }
    }

    if (node.kind === 'rect') {
      const rawW = parseFloat(htmlAdaptor.getAttribute(node, 'width') || '0');
      const rawH = parseFloat(htmlAdaptor.getAttribute(node, 'height') || '0');
      const rawX = parseFloat(htmlAdaptor.getAttribute(node, 'x') || '0');
      const rawY = parseFloat(htmlAdaptor.getAttribute(node, 'y') || '0');

      // The rect is subjected to the current scaleX and scaleY
      const x = nextX + rawX * nextScaleX;
      // When scaleY is -1, rawY > 0 becomes negative in SVG coordinates, but rules in MathJax are positioned with baseline at 0
      const y = nextY + rawY * nextScaleY;
      const w = rawW * Math.abs(nextScaleX);
      const h = rawH * Math.abs(nextScaleY);

      elements.push({
        type: 'rule',
        x: x,
        y: y,
        width: w,
        height: h
      });
    } else if (node.kind === 'path') {
      const dataC = htmlAdaptor.getAttribute(node, 'data-c') || '';
      const d = htmlAdaptor.getAttribute(node, 'd') || '';
      elements.push({
        type: 'glyph',
        char_hex: dataC,
        x: nextX,
        y: nextY,
        scale_x: nextScaleX,
        scale_y: nextScaleY,
        path_d: d
      });
    }

    for (const child of node.children || []) {
      recurse(child, nextX, nextY, nextScaleX, nextScaleY);
    }
  }

  recurse(mathNode, 0, 0, 1.0, 1.0);
  return elements;
}

function processLatex(latexString) {
  try {
    const rendered = doc.convert(latexString, {display: true});
    // In MathJax, root SVG has a g transform='scale(1,-1)'.
    // If we traverse starting from rendered, every coordinate receives scaleY = -1.
    // Instead, find the inner <g data-mml-node="math"> or pass 1.0, 1.0 ignoring the flip.
    let mathRoot = rendered;
    function findMath(n) {
      if (!n || !n.kind) return null;
      if (htmlAdaptor.getAttribute(n, 'data-mml-node') === 'math') return n;
      for (const c of (n.children || [])) {
        const found = findMath(c);
        if (found) return found;
      }
      return null;
    }
    const innerMath = findMath(rendered);
    if (innerMath) {
      mathRoot = innerMath;
    }

    const elements = extractElements(mathRoot);
    return {
      status: 'ok',
      latex: latexString,
      elements: elements
    };
  } catch (err) {
    return {
      status: 'error',
      latex: latexString,
      error: err.message || String(err)
    };
  }
}

// Read stdin or argv
if (process.argv.length > 2) {
  const latex = process.argv.slice(2).join(' ');
  const res = processLatex(latex);
  console.log(JSON.stringify(res));
} else {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => { input += chunk; });
  process.stdin.on('end', () => {
    try {
      const lines = input.split('\n').filter(l => l.trim().length > 0);
      const results = lines.map(line => {
        try {
          const parsed = JSON.parse(line);
          const latex = parsed.latex || parsed.text || line;
          return { id: parsed.id, category: parsed.category, difficulty: parsed.difficulty, ...processLatex(latex) };
        } catch {
          return processLatex(line);
        }
      });
      console.log(JSON.stringify(results));
    } catch (e) {
      console.error(e);
      process.exit(1);
    }
  });
}
