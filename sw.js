// 좋은꿈참사랑한의원 웹앱(PWA) 서비스워커
// 페이지: 네트워크 우선(새 글이 바로 보이게) → 실패하면 저장본 → 그것도 없으면 offline.html
// 그림·스타일·스크립트: 저장본 우선, 그림은 최대 200장까지만 보관
var V = "gdc-v2";
var CORE = ["/", "/index.html", "/offline.html", "/visit.html", "/style.css", "/app.js", "/app-lite.js", "/config.js", "/comfort.js",
  "/favicon.svg", "/icon-192.png", "/icon-512.png", "/manifest.webmanifest"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(V).then(function (c) {
    return Promise.all(CORE.map(function (u) { return c.add(u).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k.indexOf(V) !== 0; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(name, max) {
  caches.open(name).then(function (c) {
    c.keys().then(function (ks) { if (ks.length > max) { c.delete(ks[0]).then(function () { trim(name, max); }); } });
  });
}

self.addEventListener("fetch", function (e) {
  var r = e.request;
  if (r.method !== "GET") return;
  var u = new URL(r.url);
  if (u.origin !== location.origin) return;
  if (r.mode === "navigate" || (r.headers.get("accept") || "").indexOf("text/html") > -1) {
    e.respondWith(fetch(r).then(function (res) {
      var cp = res.clone();
      caches.open(V + "-pages").then(function (c) { c.put(r, cp); trim(V + "-pages", 60); });
      return res;
    }).catch(function () {
      return caches.match(r).then(function (m) { return m || caches.match("/offline.html"); });
    }));
    return;
  }
  if (/\.(mp4|webm|mp3|m4a)$/i.test(u.pathname)) return;
  var isImg = /\.(jpe?g|png|webp|svg|gif|ico)$/i.test(u.pathname);
  var store = isImg ? V + "-img" : V;
  e.respondWith(caches.match(r).then(function (m) {
    var net = fetch(r).then(function (res) {
      if (res && res.ok) { var cp = res.clone(); caches.open(store).then(function (c) { c.put(r, cp); if (isImg) trim(store, 200); }); }
      return res;
    }).catch(function () { return m; });
    return m || net;
  }));
});
