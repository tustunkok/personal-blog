# Client-side KaTeX with pymdown-extensions math protection

We chose to render LaTeX math in the browser using KaTeX rather than generating MathML server-side. Python-Markdown alone would mangle math content (e.g., underscores inside `$x_i$` get interpreted as Markdown italics), so we use `pymdown-extensions`' `arithmatex` extension on the server to protect math blocks from Markdown processing and wrap them in marker elements that KaTeX auto-renders on page load.

KaTeX CSS and JS are loaded unconditionally from CDN in `base.html` — every page pays the bytes, but they're cached after first load and it's simpler than per-post opt-in.

RSS feeds ship raw LaTeX since RSS readers don't run JavaScript. This is an accepted trade-off for a personal blog.

**Considered Options**: server-side MathML (rejected: adds Python dependency for LaTeX→MathML conversion, and MathML support in browsers is inconsistent), MathJax (rejected: heavier than KaTeX, slower rendering), per-post opt-in with `has_math` flag (rejected: overengineered for a single-author blog).
