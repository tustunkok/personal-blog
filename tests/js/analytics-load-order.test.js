// Regression test for the empty "Top Posts" and "Scroll Depth Distribution"
// analytics panels.
//
// The bug: base.html loads /static/js/analytics.js synchronously (no defer),
// which calls sendVisit() immediately and, on post pages, arms the heartbeat
// machinery — but both are gated on window.__post_id. post.html sets
// window.__post_id inside {% block head %}, rendered at the BOTTOM of <head>,
// AFTER analytics.js has already run. Consequences:
//   - the visit payload never carries post_id  -> Top Posts panel empty
//   - setInterval(sendHeartbeat, 30s) is never registered
//     -> no PageSessions -> Scroll Depth Distribution always empty
//
// This test renders the REAL post page HTML and runs the REAL analytics.js in
// jsdom with the exact script execution order a browser would use, capturing
// the fetch() calls and the heartbeat interval. It asserts:
//   1. the visit request carries the post id
//   2. the heartbeat interval was armed (would not be, pre-fix)
//   3. firing one heartbeat posts scroll_depth + post_id
//
// Run: node tests/js/analytics-load-order.test.js <post.html> <repo-root>
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const { JSDOM } = require("jsdom");

const htmlPath = process.argv[2];
const repoRoot = process.argv[3];
const html = fs.readFileSync(htmlPath, "utf-8");

// Parse the expected post id from the page itself (window.__post_id = N).
const postIdMatch = html.match(/window\.__post_id\s*=\s*(\d+)/);
assert(postIdMatch, "rendered post page must define window.__post_id");
const expectedPostId = Number(postIdMatch[1]);

// Rebuild the page the way a browser sees it:
//  - inline the two local scripts (fingerprint.js, analytics.js) AT their
//    original positions, so synchronous execution order is preserved exactly
//  - drop every other external script/link (CDNs, fonts) so jsdom needs no
//    network and runs instantly
const localScripts = {};
for (const name of ["fingerprint.js", "analytics.js"]) {
  localScripts[name] = fs.readFileSync(
    path.join(repoRoot, "app", "static", "js", name),
    "utf-8"
  );
}

const rebuilt = html
  .replace(/<script src="\/static\/js\/(fingerprint|analytics)\.js"><\/script>/g, (m, name) => {
    return "<script>" + localScripts[name + ".js"] + "<\/script>";
  })
  .replace(/<script[^>]*src="(?:https?:)?\/\/[^"]*"[^>]*><\/script>/g, "")
  .replace(/<script>\s*tailwind\.config[^<]*<\/script>/g, "")
  .replace(/<link[^>]*rel="stylesheet"[^>]*>/g, "");

(async function main() {
  // Stub fetch (capture requests; answer the visit call with a visit_id so the
  // heartbeat machinery has something to report) and setInterval (capture the
  // callback instead of scheduling, so the test is instant and never hangs).
  const stubScript = `
(function () {
  window.__capturedRequests = [];
  window.__armedIntervals = [];
  window.__heartbeatFn = null;
  window.matchMedia = function () {
    return { matches: false, addListener: function () {}, removeListener: function () {}, addEventListener: function () {}, removeEventListener: function () {} };
  };
  window.setInterval = function (fn, ms) {
    window.__armedIntervals.push(ms);
    if (ms === 30000) window.__heartbeatFn = fn;
    return 1;
  };
  window.fetch = function (url, opts) {
    var urlStr = String(url);
    window.__capturedRequests.push({ url: urlStr, body: (opts && opts.body) || null });
    if (urlStr.indexOf("/api/analytics/visit") !== -1) {
      return Promise.resolve({ json: function () { return Promise.resolve({ visit_id: 42 }); } });
    }
    return Promise.resolve({ json: function () { return Promise.resolve({}); } });
  };
})();
`;

  const dom = new JSDOM(rebuilt, {
    runScripts: "dangerously",
    url: "https://blog.example/posts/p",
    beforeParse(window) {
      window.eval(stubScript);
    },
  });

  try {
    const requests = dom.window.__capturedRequests || [];

    // 1) The visit payload must carry post_id (Top Posts panel).
    const visitReq = requests.find((r) => r.url.indexOf("/api/analytics/visit") !== -1);
    assert(visitReq, "analytics.js must POST /api/analytics/visit on page load");
    const visitBody = JSON.parse(visitReq.body);
    assert(
      visitBody.post_id === expectedPostId,
      "visit payload must carry post_id=" + expectedPostId +
      " (got: " + JSON.stringify(visitBody) + ") — analytics.js ran before " +
      "window.__post_id was defined, so post_id is dropped and the Top Posts " +
      "panel can never show data"
    );

    // 2) The heartbeat interval must be armed (Scroll Depth Distribution panel).
    assert(
      dom.window.__armedIntervals.indexOf(30000) !== -1,
      "heartbeat interval was never registered — analytics.js saw window.__post_id " +
      "as undefined, so no PageSessions are ever recorded and the Scroll Depth " +
      "Distribution panel stays empty"
    );

    // 3) Firing one heartbeat must report scroll_depth + post_id.
    //    (flush the visit-response microtask first so visitId is set)
    await new Promise((r) => setTimeout(r, 0));
    assert(dom.window.__heartbeatFn, "heartbeat callback must be captured");
    dom.window.__heartbeatFn();

    const hbReq = requests.find((r) => r.url.indexOf("/api/analytics/heartbeat") !== -1);
    assert(hbReq, "armed heartbeat must POST /api/analytics/heartbeat");
    const hbBody = JSON.parse(hbReq.body);
    assert(
      hbBody.post_id === expectedPostId,
      "heartbeat payload must carry post_id (got: " + JSON.stringify(hbBody) + ")"
    );
    assert(
      typeof hbBody.scroll_depth === "number",
      "heartbeat payload must carry a numeric scroll_depth (got: " + JSON.stringify(hbBody) + ")"
    );

    console.log(
      "OK: visit carried post_id=" + expectedPostId +
      "; heartbeat armed and fired with scroll_depth=" + hbBody.scroll_depth
    );
  } finally {
    dom.window.close();
  }
})().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
