// Highlight synchronously instead of hljs.highlightAll(): while the document is
// still loading, highlightAll() defers to DOMContentLoaded, which would
// re-tokenize each block AFTER the line numbers below are injected — destroying
// them and gluing the digits into the code text.
if (window.hljs) {
    document.querySelectorAll("pre code").forEach(function (el) {
        hljs.highlightElement(el);
    });
}

document.querySelectorAll("pre > code").forEach(function (codeBlock) {
    var pre = codeBlock.parentNode;

    var match = codeBlock.className.match(/language-(\S+)/);
    var lang = match ? match[1] : "";
    var filename = "";

    if (lang && lang.indexOf("filename=") !== -1) {
        filename = lang.split("filename=")[1] || "";
        lang = lang.split("filename=")[0] || "";
    }

    if (filename) {
        var header = document.createElement("div");
        header.className = "code-filename";
        header.textContent = filename;
        pre.parentNode.insertBefore(header, pre);
    }

    if (lang) {
        var langLabel = document.createElement("div");
        langLabel.className = "code-lang";
        langLabel.textContent = lang;
        pre.style.position = "relative";
        pre.appendChild(langLabel);
    }

    var copyBtn = document.createElement("button");
    copyBtn.className = "code-copy";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(codeText(codeBlock)).then(function () {
            copyBtn.textContent = "Copied!";
            setTimeout(function () {
                copyBtn.textContent = "Copy";
            }, 2000);
        });
    });
    pre.style.position = "relative";
    pre.appendChild(copyBtn);

    var lines = codeBlock.innerHTML.split("\n");
    if (lines.length > 1) {
        var numbered = "";
        for (var i = 0; i < lines.length; i++) {
            numbered += '<span class="line-number">' + (i + 1) + "</span>" + lines[i];
            if (i < lines.length - 1) {
                numbered += "\n";
            }
        }
        codeBlock.innerHTML = numbered;
    }
});

// Plain text of the code, excluding the injected line-number spans.
function codeText(el) {
    var text = "";
    el.childNodes.forEach(function (node) {
        if (node.nodeType === 3) {
            text += node.textContent;
        } else if (node.nodeType === 1) {
            if (node.classList && node.classList.contains("line-number")) {
                return;
            }
            text += codeText(node);
        }
    });
    return text;
}
