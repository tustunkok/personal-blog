hljs.highlightAll();

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
        navigator.clipboard.writeText(codeBlock.textContent).then(function () {
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
        for (var i = 0; i < lines.length - 1; i++) {
            numbered += '<span class="line-number">' + (i + 1) + "</span>" + lines[i] + "\n";
        }
        numbered += lines[lines.length - 1];
        codeBlock.innerHTML = numbered;
    }
});
