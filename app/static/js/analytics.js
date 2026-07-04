(function () {
    var HEARTBEAT_INTERVAL = 30000;
    var SCROLL_MILESTONES = [0.25, 0.50, 0.75, 1.0];
    var reachedMilestones = {};
    var visitId = null;
    var postId = null;
    var endReachedSent = false;

    function getFpHash() {
        return window.__fp_hash || null;
    }

    function sendVisit() {
        var body = {
            path: window.location.pathname,
            fingerprint_hash: getFpHash(),
            referrer: document.referrer || null
        };
        if (window.__post_id) body.post_id = window.__post_id;
        fetch('/api/analytics/visit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                visitId = data.visit_id;
                window.__visit_id = visitId;
            })
            .catch(function () {});
    }

    function sendHeartbeat() {
        if (!visitId) return;
        var docH = document.documentElement;
        var totalH = docH.scrollHeight - window.innerHeight;
        var scrollDepth = totalH > 0 ? Math.min(window.scrollY / totalH, 1) : 1;

        var foundMilestone = false;
        SCROLL_MILESTONES.forEach(function (m) {
            if (scrollDepth >= m && !reachedMilestones[m]) {
                reachedMilestones[m] = true;
                foundMilestone = true;
            }
        });

        fetch('/api/analytics/heartbeat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                visit_id: visitId,
                post_id: window.__post_id || null,
                scroll_depth: parseFloat(scrollDepth.toFixed(4)),
                end_reached: endReachedSent
            })
        }).catch(function () {});
    }

    function sendEvent(type, data) {
        if (!visitId) return;
        fetch('/api/analytics/event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                visit_id: visitId,
                event_type: type,
                post_id: window.__post_id || null,
                data: data
            })
        }).catch(function () {});
    }

    function sendNavigation(fromUrl) {
        if (!visitId) return;
        fetch('/api/analytics/navigate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                visit_id: visitId,
                from_url: fromUrl,
                to_url: window.location.pathname
            })
        }).catch(function () {});
    }

    function initEngagementListeners() {
        document.addEventListener('click', function (e) {
            var target = e.target;
            while (target && target !== document) {
                if (target.tagName === 'A' && target.href) {
                    var href = target.getAttribute('href');
                    var isExternal = href && (href.indexOf('http://') === 0 || href.indexOf('https://') === 0);
                    if (isExternal) {
                        sendEvent('external_link_click', { url: href });
                    }
                    break;
                }
                target = target.parentElement;
            }
        });

        document.addEventListener('copy', function (e) {
            var selection = window.getSelection().toString().substring(0, 200);
            if (selection) {
                sendEvent('copy', { text: selection });
            }
        });

        document.addEventListener('mouseup', function () {
            var selection = window.getSelection().toString();
            if (selection && selection.length >= 10) {
                sendEvent('text_selection', { length: selection.length });
            }
        });

        document.addEventListener('click', function (e) {
            var target = e.target;
            while (target && target !== document) {
                if ((target.tagName === 'CODE' && target.parentElement && target.parentElement.tagName === 'PRE') ||
                    target.classList.contains('code-block-wrapper') ||
                    (target.tagName === 'PRE' && target.querySelector('code'))) {
                    sendEvent('code_block_click', null);
                    break;
                }
                target = target.parentElement;
            }
        });
    }

    function checkEndReached() {
        if (endReachedSent) return;
        var docH = document.documentElement;
        var totalH = docH.scrollHeight - window.innerHeight;
        if (totalH > 0 && window.scrollY >= totalH - 100) {
            endReachedSent = true;
            fetch('/api/analytics/heartbeat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    visit_id: visitId,
                    post_id: window.__post_id || null,
                    scroll_depth: 1.0,
                    end_reached: true
                })
            }).catch(function () {});
        }
    }

    sendVisit();

    var prevUrl = null;
    try { prevUrl = sessionStorage.getItem('__prev_url'); } catch (e) {}
    if (prevUrl && prevUrl !== window.location.pathname) {
        setTimeout(function () {
            sendNavigation(prevUrl);
        }, 500);
    }
    try { sessionStorage.setItem('__prev_url', window.location.pathname); } catch (e) {}

    if (window.__post_id) {
        initEngagementListeners();
        setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
        window.addEventListener('scroll', checkEndReached);
    }
})();
