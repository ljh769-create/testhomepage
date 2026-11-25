/* 움직임(원장님 디자인 원칙 4-01): 스크롤 나타나기·숫자 올라가기·첫 화면 깊이감·사진 확대·마우스 기울기.
   '움직임 줄이기' 설정이거나 오래된 브라우저면 아무것도 하지 않는다(내용은 그대로 보임). 외부 라이브러리 없음. */
(function () {
  var mm = window.matchMedia;
  if ((mm && mm("(prefers-reduced-motion: reduce)").matches) || !("IntersectionObserver" in window)) return;
  document.documentElement.classList.add("mo");

  function countUp(el) {
    var n = +el.getAttribute("data-n") || 0, t0 = 0, dur = 1200;
    function step(t) {
      if (!t0) t0 = t;
      var p = Math.min((t - t0) / dur, 1);
      el.textContent = Math.round(n * (1 - Math.pow(1 - p, 3))).toLocaleString("ko-KR");
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      e.target.classList.add("mo-in");
      if (e.target.hasAttribute("data-n")) countUp(e.target);
      io.unobserve(e.target);
    });
  }, { threshold: 0.14, rootMargin: "0px 0px -6% 0px" });
  document.querySelectorAll("[data-mo],[data-n]").forEach(function (el) { io.observe(el); });
  document.querySelectorAll('[data-mo="stagger"]').forEach(function (ul) {
    Array.prototype.forEach.call(ul.children, function (li, i) { li.style.transitionDelay = Math.min(i * 70, 840) + "ms"; });
  });
  // 아직 화면에 안 들어온 숫자는 0부터 올라가게
  document.querySelectorAll("[data-n]").forEach(function (el) {
    var r = el.getBoundingClientRect();
    if (r.top > innerHeight) el.textContent = "0";
  });

  var hero = document.querySelector(".phero>img"), heroIn = document.querySelector(".phero-in");
  var cines = Array.prototype.slice.call(document.querySelectorAll(".cine img"));
  var busy = false;
  function frame() {
    busy = false;
    var y = window.scrollY, h = innerHeight;
    if (hero && y < h * 1.2) {
      hero.style.translate = "0 " + (y * 0.28).toFixed(1) + "px";
      if (heroIn) heroIn.style.opacity = Math.max(0, 1 - y / (h * 0.7)).toFixed(3);
    }
    cines.forEach(function (im) {
      var r = im.parentNode.getBoundingClientRect();
      if (r.bottom < 0 || r.top > h) return;
      var p = (h - r.top) / (h + r.height);
      im.style.transform = "scale(" + (1.14 - p * 0.1).toFixed(4) + ") translate3d(0," + ((p - 0.5) * -26).toFixed(1) + "px,0)";
    });
  }
  addEventListener("scroll", function () { if (!busy) { busy = true; requestAnimationFrame(frame); } }, { passive: true });
  frame();

  if (mm && mm("(hover:hover) and (pointer:fine)").matches) {
    document.querySelectorAll(".tilt").forEach(function (el) {
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        el.style.setProperty("--rx", ((0.5 - y) * 9).toFixed(2) + "deg");
        el.style.setProperty("--ry", ((x - 0.5) * 11).toFixed(2) + "deg");
        el.style.setProperty("--gx", (x * 100).toFixed(1) + "%");
        el.style.setProperty("--gy", (y * 100).toFixed(1) + "%");
      });
      el.addEventListener("pointerleave", function () { el.style.setProperty("--rx", "0deg"); el.style.setProperty("--ry", "0deg"); });
    });
  }
})();
