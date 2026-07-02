document.addEventListener("paste", function (event) {
    var items = event.clipboardData && event.clipboardData.items;
    if (!items) return;

    for (var i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") === -1) continue;

        event.preventDefault();

        var blob = items[i].getAsFile();
        var formData = new FormData();
        formData.append("file", blob, "pasted-image.png");

        var inserting = document.createElement("span");
        inserting.textContent = "Uploading image...";
        var cm = easyMDE.codemirror;
        cm.replaceSelection(inserting.outerHTML);
        cm.focus();

        fetch("/admin/images/upload", {
            method: "POST",
            body: formData,
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var markdown = "![](/images/" + data.id + ")";
                var cursor = cm.getCursor();
                var line = cursor.line;
                var from = { line: line, ch: 0 };
                var to = { line: line, ch: cm.getLine(line).length };
                cm.replaceRange(markdown, from, to);
            })
            .catch(function () {
                var line = cm.getCursor().line;
                var from = { line: line, ch: 0 };
                var to = { line: line, ch: cm.getLine(line).length };
                cm.replaceRange("", from, to);
            });

        break;
    }
});
