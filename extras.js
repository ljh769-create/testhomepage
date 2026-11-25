/* 좋은꿈참사랑한의원 — 작은 편의 기능(2026-11-26, 원장님: 백록담한의원 참고)
   1) 머리글 '지금 진료 중' 표시  2) 홈 증상 검색  3) PC 오른쪽 고정 버튼(전화·예약·길찾기·카톡)
   진료시간: 평일 09:30~20:00(점심 13:00~14:00), 토·일·공휴일 09:30~15:00 — 공휴일은 따로 알 수 없어 주말 기준으로만 표시 */
(function () {
  var TEL = "tel:028157510", BOOK = "https://booking.naver.com/booking/13/bizes/1043468",
      MAP = "https://map.naver.com/p/entry/place/13157244", KAKAO = "https://pf.kakao.com/_UWxnvb";
  var root = (document.querySelector('script[src$="extras.js"]') || {}).getAttribute ? document.querySelector('script[src$="extras.js"]').getAttribute("src").replace(/extras\.js$/, "") : "";

  /* 진료실 설명 모드: 주소에 ?big 이 있으면 큰 글씨, 예약 버튼 숨김(explain.html 에서 연 글) */
  if (/[?&]big\b/.test(location.search)) document.documentElement.classList.add("bigread");

  var css = ""
    + ".livebadge{display:inline-flex;align-items:center;gap:6px;font:500 12.5px/1.2 'Noto Sans KR',sans-serif;letter-spacing:-.02em;color:#1f3552;background:#eef4fb;border:1px solid #dce8f5;border-radius:999px;padding:5px 10px;margin-left:10px;white-space:nowrap;vertical-align:middle}"
    + ".livebadge i{width:7px;height:7px;border-radius:50%;background:#9aa7b8;display:inline-block}"
    + ".livebadge.on i{background:#2fae66;box-shadow:0 0 0 3px rgba(47,174,102,.18)}"
    + ".livebadge.lunch i{background:#e0a100}"
    + "@media (max-width:520px){.livebadge{font-size:11.5px;padding:4px 8px;margin-left:6px}}"
    + ".symsearch{max-width:760px;margin:36px auto 8px;padding:28px 24px;background:#fff;border:1px solid #dce8f5;border-radius:22px}"
    + ".symsearch h2{margin:0 0 6px;font-size:clamp(22px,5.4vw,28px)}"
    + ".symsearch p.sub{margin:0 0 16px;color:#5b6475;font-size:15px}"
    + ".symsearch form{display:flex;gap:8px}"
    + ".symsearch input{flex:1;min-width:0;font:400 17px 'Noto Sans KR',sans-serif;padding:13px 16px;border:1.5px solid #c9d7e8;border-radius:14px;outline:none}"
    + ".symsearch input:focus{border-color:#1f3552}"
    + ".symsearch button{font:500 16px 'Noto Sans KR',sans-serif;padding:0 18px;border:0;border-radius:14px;background:#1f3552;color:#fff;cursor:pointer;white-space:nowrap}"
    + ".symsearch .tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}"
    + ".symsearch .tags button{background:#eef4fb;color:#1f3552;font-size:14px;padding:6px 12px;border-radius:999px}"
    + ".symsearch ul{list-style:none;margin:16px 0 0;padding:0}"
    + ".symsearch li a{display:block;padding:12px 4px;border-top:1px solid #eef2f7;color:#1f2a3a;text-decoration:none}"
    + ".symsearch li a small{display:block;color:#6b7280;font-size:13px;margin-top:2px}"
    + ".symsearch .none{margin-top:14px;color:#5b6475;font-size:15px}"
    + ".floatacts{display:none}"
    + "@media (min-width:1024px){.floatacts{display:flex;flex-direction:column;gap:10px;position:fixed;right:22px;bottom:110px;z-index:30}"
    + ".floatacts a{display:flex;flex-direction:column;align-items:center;justify-content:center;width:62px;height:62px;border-radius:50%;background:#fff;border:1px solid #dce8f5;box-shadow:0 6px 18px rgba(31,53,82,.12);color:#1f3552;text-decoration:none;font:500 11.5px 'Noto Sans KR',sans-serif;letter-spacing:-.02em}"
    + ".floatacts a svg{width:20px;height:20px;margin-bottom:3px}"
    + ".floatacts a.book{background:#1f3552;color:#fff;border-color:#1f3552}"
    + ".floatacts a:hover{transform:translateY(-1px)}"
    + ".actbar{display:none!important}body{padding-bottom:0!important}}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);

  /* 1) 지금 진료 중 */
  function status() {
    var now = new Date();
    var k = new Date(now.getTime() + (now.getTimezoneOffset() + 540) * 60000); // 한국 시간
    var d = k.getDay(), m = k.getHours() * 60 + k.getMinutes(), weekend = (d === 0 || d === 6);
    var open = 570, close = weekend ? 900 : 1200;
    if (m < open) return ["", "진료 전 · 09:30 시작"];
    if (!weekend && m >= 780 && m < 840) return ["lunch", "점심시간 · 14:00 다시 진료"];
    if (m < close) return ["on", "지금 진료 중 · " + (weekend ? "15:00" : "20:00") + "까지"];
    return ["", "오늘 진료 마감 · 내일 09:30"];
  }
  function paintBadge() {
    var host = document.querySelector("header.top .brand, header.top a[href$='index.html'], header.top");
    if (!host) return;
    var b = document.querySelector(".livebadge");
    if (!b) { b = document.createElement("span"); b.className = "livebadge"; b.innerHTML = "<i></i><span></span>"; b.setAttribute("aria-live", "polite");
      var anchor = document.querySelector("header.top .bar > div") || host; anchor.appendChild(b); }
    var s = status(); b.className = "livebadge" + (s[0] ? " " + s[0] : ""); b.lastChild.textContent = s[1];
  }

  /* 3) PC 오른쪽 고정 버튼 */
  function floatActs() {
    if (document.querySelector(".floatacts")) return;
    var ic = {
      tel: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/></svg>',
      book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M9 15l2 2 4-4"/></svg>',
      map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 22s7-6.2 7-12a7 7 0 1 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>',
      talk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.2A8 8 0 1 1 21 12z"/></svg>'
    };
    var w = document.createElement("nav"); w.className = "floatacts"; w.setAttribute("aria-label", "바로가기");
    w.innerHTML = '<a href="' + TEL + '" data-cta="float_tel">' + ic.tel + '전화</a>'
      + '<a class="book" href="' + BOOK + '" target="_blank" rel="noopener" data-cta="float_book">' + ic.book + '예약</a>'
      + '<a href="' + MAP + '" target="_blank" rel="noopener" data-link-location="float_map">' + ic.map + '길찾기</a>'
      + '<a href="' + KAKAO + '" target="_blank" rel="noopener" data-cta="float_kakao">' + ic.talk + '카톡</a>';
    document.body.appendChild(w);
  }

  /* 2) 홈 증상 검색 */
  function search() {
    var box = document.getElementById("symsearch");
    if (!box) return;
    var input = box.querySelector("input"), list = box.querySelector("ul"), none = box.querySelector(".none"), posts = null;
    function load(cb) {
      if (posts) return cb();
      fetch(root + "data/posts.json").then(function (r) { return r.json(); }).then(function (d) { posts = d; cb(); }).catch(function () { posts = []; cb(); });
    }
    function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }
    function run(q) {
      q = (q || "").trim(); if (!q) { list.innerHTML = ""; none.hidden = true; return; }
      load(function () {
        var words = q.split(/\s+/).map(norm).filter(Boolean);
        var hits = posts.map(function (p) {
          var hay = norm(p.t) + "|" + norm(p.n), sc = 0;
          words.forEach(function (w) { if (norm(p.t).indexOf(w) > -1) sc += 3; else if (hay.indexOf(w) > -1) sc += 1; });
          return [sc, p];
        }).filter(function (x) { return x[0] > 0; }).sort(function (a, b) { return b[0] - a[0]; }).slice(0, 8);
        list.innerHTML = hits.map(function (x) { var p = x[1];
          return '<li><a data-link-location="search" href="' + root + p.u + '">' + p.t.replace(/</g, "&lt;") + "<small>" + (p.n || "") + "</small></a></li>"; }).join("");
        none.hidden = hits.length > 0;
        if (window.gtag) try { gtag("event", "search", { search_term: q }); } catch (e) {}
      });
    }
    box.querySelector("form").addEventListener("submit", function (e) { e.preventDefault(); run(input.value); });
    var t; input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { run(input.value); }, 250); });
    box.querySelectorAll(".tags button").forEach(function (b) { b.addEventListener("click", function () { input.value = b.textContent; run(b.textContent); }); });
  }

  function init() { paintBadge(); floatActs(); search(); setInterval(paintBadge, 60000); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
