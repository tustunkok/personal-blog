function createEasyMDE(elementId) {
    return new EasyMDE({
        element: document.getElementById(elementId),
        previewRender: function(plainText, preview) {
            var html = this.parent.markdown(plainText);
            html = html.replace(
                /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g,
                '<pre class="mermaid">$1</pre>'
            );
            setTimeout(function() {
                if (typeof renderMathInElement === 'function') {
                    renderMathInElement(preview, {delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false}
                    ]});
                }
                var mermaidPreviews = preview.querySelectorAll('.mermaid');
                if (mermaidPreviews.length > 0 && typeof mermaid !== 'undefined') {
                    mermaid.run({ nodes: mermaidPreviews });
                }
            }, 10);
            return html;
        }
    });
}
