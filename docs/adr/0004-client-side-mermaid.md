# Client-side mermaid diagram rendering

Mermaid diagrams (```````mermaid``````` fenced blocks) are rendered client-side by mermaid.js — same pattern as KaTeX for math. The server outputs a `<pre class="mermaid">` container with the raw diagram definition; mermaid.js converts it to SVG in the browser.

**Why client-side**: Consistent with existing KaTeX/highlight.js pattern. Avoids a heavy server-side dependency (headless browser or CLI). Mermaid diagrams are content authored intentionally — the author knows JS is required to see them, same as math blocks.

**Considered**: Server-side SVG generation via playwright or mermaid-cli. Rejected because it adds deployment complexity (Chromium dependency, subprocess management) for no clear win — diagrams in RSS/OG is an edge case, and even with server-side rendering the CDN for the SVG interactivity version would still be needed.
