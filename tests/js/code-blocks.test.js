// Regression test for the code-blocks.js line-number bug.
//
// The bug: hljs.highlightAll() defers to DOMContentLoaded while the document is
// still loading. code-blocks.js then injected line numbers synchronously into
// the *unhighlighted* HTML; when the deferred highlight ran, it re-tokenized
// the text including the injected digits — destroying the line-number spans and
// gluing numbers into the code (e.g. "31. Read the PRD...").
//
// This test runs the REAL code-blocks.js inside jsdom with the REAL highlight.js
// (same version as the CDN in post.html) during document parse, then asserts the
// final DOM invariants.
//
// Run: node tests/js/code-blocks.test.js   (after `npm install` in tests/js)
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const { JSDOM } = require("jsdom");

const repoRoot = path.join(__dirname, "..", "..");
const codeBlocksJs = fs.readFileSync(
  path.join(repoRoot, "app", "static", "js", "code-blocks.js"),
  "utf-8"
);

// highlight.js is CommonJS; build the same instance the CDN bundle would create
// (core + the languages used by the test blocks) inside the jsdom window.
const hljsDir = path.join(__dirname, "node_modules", "highlight.js", "lib");
const coreSrc = fs.readFileSync(path.join(hljsDir, "core.js"), "utf-8");
const bashSrc = fs.readFileSync(path.join(hljsDir, "languages", "bash.js"), "utf-8");
const jsonSrc = fs.readFileSync(path.join(hljsDir, "languages", "json.js"), "utf-8");

const hljsBuildScript = `
(function () {
  var coreMod = { exports: {} };
  (new Function("module", "exports", ${JSON.stringify(coreSrc)}))(coreMod, coreMod.exports);
  var hljs = coreMod.exports;
  function register(name, src) {
    var m = { exports: {} };
    (new Function("module", "exports", src))(m, m.exports);
    hljs.registerLanguage(name, m.exports);
  }
  register("bash", ${JSON.stringify(bashSrc)});
  register("json", ${JSON.stringify(jsonSrc)});
  window.hljs = hljs;
})();
`;

const blocks = [
  {
    lang: "bash",
    code: `#!/bin/bash
opencode run -p --auto "@PRD.md @progress.txt
1. Read the PRD and progress file.
2. Find the next incomplete task and implement it.
3. Commit your changes.
4. Update progress.txt with what you did.
ONLY DO ONE TASK AT A TIME."`,
  },
  {
    lang: "bash",
    code: `git config --global user.name "You"
git config --global user.email "you@example.com"`,
  },
  {
    lang: "bash",
    code: `#!/bin/bash
set -e
if [ -z "$1" ]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi
for ((i=1; i<=$1; i++)); do
  result=$(opencode run -p --auto "@PRD.md @progress.txt
1. Find the highest-priority task and implement it.
2. Run your tests and type checks.
3. Update the PRD with what was done.
4. Append your progress to progress.txt.
5. Commit your changes.
ONLY WORK ON A SINGLE TASK.
If the PRD is complete, output <promise>COMPLETE</promise>.")
  echo "$result"
done`,
  },
  // single-line block: no line numbers expected by design
  { lang: "bash", code: `touch progress.txt` },
];

// Escape for embedding in HTML text (highlight.js must see raw text).
const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const blockHtml = blocks
  .map(
    (b) =>
      `<pre class="highlight"><code class="language-${b.lang}">${escapeHtml(b.code)}</code></pre>`
  )
  .join("\n");

// Inline the scripts so they execute during parse, when document.readyState is
// "loading" — the exact condition under which highlightAll() defers.
const html = `<!DOCTYPE html><html><body>${blockHtml}<script>${hljsBuildScript}</script><script>${codeBlocksJs}</script></body></html>`;

const dom = new JSDOM(html, { runScripts: "dangerously" });

setTimeout(() => {
  const doc = dom.window.document;
  const codes = [...doc.querySelectorAll("pre > code")];

  // Text of a code element excluding the injected line-number spans.
  const withoutLineNumbers = (el) =>
    [...el.childNodes]
      .map((n) =>
        n.nodeType === 3
          ? n.textContent
          : n.classList && n.classList.contains("line-number")
            ? ""
            : withoutLineNumbers(n)
      )
      .join("");

  codes.forEach((code, idx) => {
    const original = blocks[idx].code;
    const lineCount = original.split("\n").length;
    if (lineCount < 2) return; // single-line blocks are intentionally unnumbered

    const numbers = [...code.querySelectorAll("span.line-number")].map((s) => s.textContent);
    const expectedNumbers = Array.from({ length: lineCount }, (_, i) => String(i + 1));

    assert.deepStrictEqual(
      numbers,
      expectedNumbers,
      `block ${idx}: expected one sequential line number per line (incl. last), got ${JSON.stringify(numbers)}`
    );
    assert.strictEqual(
      withoutLineNumbers(code),
      original,
      `block ${idx}: line numbers must not leak into the code text`
    );
  });

  // Copy button must copy the code without line numbers.
  const copied = dom.window.eval(`(function () {
    var captured = null;
    navigator.clipboard = { writeText: function (t) { captured = t; return Promise.resolve(); } };
    var code = document.querySelectorAll("pre > code")[0];
    code.parentNode.querySelector(".code-copy").click();
    return captured;
  })()`);
  assert.strictEqual(copied, blocks[0].code, "copy must exclude line numbers");

  console.log("code-blocks.js: all assertions passed");
  process.exit(0);
}, 100);
