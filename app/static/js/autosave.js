(() => {
    const form = document.querySelector("form#edit-post-form");
    if (!form) return;

    const postId = form.dataset.postId;
    if (!postId) return;

    const titleEl = form.querySelector("[name='title']");
    const bodyEl = form.querySelector("[name='body']");
    const excerptEl = form.querySelector("[name='excerpt']");
    if (!titleEl || !bodyEl) return;

    let dirty = false;

    function markDirty() {
        dirty = true;
    }

    titleEl.addEventListener("input", markDirty);
    bodyEl.addEventListener("input", markDirty);
    if (excerptEl) excerptEl.addEventListener("input", markDirty);

    function doAutosave() {
        if (!dirty) return;
        const formData = new FormData();
        formData.append("title", titleEl.value);
        formData.append("body", bodyEl.value);
        if (excerptEl) formData.append("excerpt", excerptEl.value);

        fetch("/admin/posts/" + postId + "/autosave", {
            method: "POST",
            body: formData,
        }).then(() => {
            dirty = false;
        }).catch(() => {});
    }

    setInterval(doAutosave, 5 * 60 * 1000);
})();
