(function () {
    var STORAGE_KEY = 'fp_hash';

    function collectFingerprint() {
        var n = navigator;
        return {
            screen_resolution: screen.width + 'x' + screen.height,
            color_depth: screen.colorDepth,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            os: (n.platform || 'unknown'),
            browser: getBrowser(),
            browser_version: getBrowserVersion(),
            touch_support: n.maxTouchPoints > 0,
            languages: (n.languages || []).join(','),
            do_not_track: n.doNotTrack === '1',
            reduced_motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
            cpu_cores: n.hardwareConcurrency || null,
            memory_gb: n.deviceMemory || null,
            connection_type: getConnectionType(),
            dark_mode_preferred: window.matchMedia('(prefers-color-scheme: dark)').matches
        };
    }

    function getBrowser() {
        var ua = navigator.userAgent;
        if (ua.indexOf('Firefox') > -1) return 'Firefox';
        if (ua.indexOf('Edg') > -1) return 'Edge';
        if (ua.indexOf('Chrome') > -1) return 'Chrome';
        if (ua.indexOf('Safari') > -1) return 'Safari';
        return 'Other';
    }

    function getBrowserVersion() {
        var ua = navigator.userAgent;
        var m = ua.match(/(Firefox|Chrome|Safari|Edg)\/(\d+)/);
        return m ? m[2] : null;
    }

    function getConnectionType() {
        var c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (c && c.effectiveType) return c.effectiveType;
        return null;
    }

    function registerFingerprint(payload) {
        fetch('/api/analytics/fingerprint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                try { localStorage.setItem(STORAGE_KEY, data.fingerprint_hash); } catch (e) {}
                window.__fp_hash = data.fingerprint_hash;
            })
            .catch(function () {});
    }

    try {
        var cached = localStorage.getItem(STORAGE_KEY);
        if (cached) {
            window.__fp_hash = cached;
        }
    } catch (e) {}

    var fp = collectFingerprint();
    registerFingerprint(fp);
})();
