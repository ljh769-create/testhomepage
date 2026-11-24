// 글 페이지용 경량 스크립트: 전화 링크 설정(config.js 없이 site 기본값 사용)과 스크롤 등장 효과
(function(){
  var rv=document.querySelectorAll(".reveal");
  if("IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);}});},{threshold:.12});
    rv.forEach(function(el){io.observe(el);});
  }else{rv.forEach(function(el){el.classList.add("in");});}
})();

if("serviceWorker" in navigator&&location.protocol==="https:"){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(){});});}

// 모든 페이지 공통 하단 고정 바: 예약하기(네이버 예약) · 전화 · 카카오톡 상담
(function(){
  if(window.__actbar)return;window.__actbar=1;
  function run(){
    if(document.querySelector(".actbar"))return;
    var c=window.SITE_NOW||window.SITE_CONFIG||{};
    var book=/^https?:\/\//.test(c.booking||"")?c.booking:"https://booking.naver.com/booking/13/bizes/1043468";
    var ph=(c.phone||"02-815-7510"),pn=ph.replace(/[^0-9+]/g,"");
    var bar=document.querySelector(".fixed")||document.createElement("div");
    bar.className="fixed actbar";bar.setAttribute("role","navigation");bar.setAttribute("aria-label","예약·상담 바로가기");
    bar.innerHTML='<a class="btn primary" href="'+book+'" target="_blank" rel="noopener">예약하기</a>'+
      '<a class="btn" href="tel:'+pn+'" aria-label="전화 '+ph+'">전화</a>'+
      '<a class="btn kakao" href="https://pf.kakao.com/_UWxnvb/chat" target="_blank" rel="noopener">카카오톡 상담</a>';
    if(!bar.parentNode)document.body.appendChild(bar);
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",run);else run();
})();
