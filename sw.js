// Match Cards のサービスワーカー
// 画面・エンブレム：保存したものを先に使う（すばやく開く・電波がなくても開ける）
// 試合データ（data/app.json）：まずネットから取り、取れなければ保存した前回のデータ
const VERSION = "mc-v1";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const sameOrigin = url.origin === location.origin;
  const isData = sameOrigin && url.pathname.endsWith("/data/app.json");
  const isPage = req.mode === "navigate";
  if (isData || isPage) {
    // ネット優先
    e.respondWith(fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(isPage ? "index.html" : req, copy)); }
      return res;
    }).catch(() => caches.match(isPage ? "index.html" : req, {ignoreSearch: true})));
    return;
  }
  if (sameOrigin || url.hostname.endsWith("gstatic.com") || url.hostname.endsWith("googleapis.com")) {
    // 保存優先（エンブレム・フォントなど）
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(VERSION).then(c => c.put(req, copy)); }
      return res;
    })));
  }
});
