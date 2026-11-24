(function(){
  var KEY="goodDreamSiteConfig";
  var cfg=Object.assign({booking:"",address:"",hours:"",phone:""},window.SITE_CONFIG||{});
  try{var saved=JSON.parse(localStorage.getItem(KEY)||"{}");Object.keys(saved).forEach(function(k){if(saved[k])cfg[k]=saved[k];});}catch(e){}
  window.SITE_NOW=cfg;

  function safeUrl(u){return /^(https?:\/\/|tel:)/i.test(u)?u:"";}

  var bookBtn=document.getElementById("book-btn");
  var bookLink=document.getElementById("book-link");
  var url=safeUrl(cfg.booking);
  if(bookBtn){
    if(url){bookBtn.href=url;bookBtn.target="_blank";bookBtn.rel="noopener";}
    else{bookBtn.href="#visit";}
  }
  if(bookLink){
    if(url){bookLink.href=url;bookLink.target="_blank";bookLink.rel="noopener";bookLink.hidden=false;}
    else{bookLink.hidden=true;}
  }
  function fill(id,val){
    var el=document.getElementById(id);if(!el)return;
    if(val){el.textContent=val;el.className="";}
    else{el.textContent="준비 중입니다. 한의원에 문의해 주세요.";el.className="note";}
  }
  fill("info-address",cfg.address);
  fill("info-hours",cfg.hours);
  var topCall=document.getElementById("top-call");
  var pn=cfg.phone.replace(/[^0-9+]/g,"");
  if(topCall&&pn){topCall.href="tel:"+pn;topCall.textContent="전화 문의";}
  var pause=document.getElementById("pause");
  if(pause){pause.addEventListener("click",function(){
    var on=document.body.classList.toggle("paused");
    pause.setAttribute("aria-pressed",on);pause.textContent=on?"움직임 다시 켜기":"움직임 멈추기";
  });}
  var rv=document.querySelectorAll(".reveal");
  if("IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);}});},{threshold:.12});
    rv.forEach(function(el){io.observe(el);});
  }else{rv.forEach(function(el){el.classList.add("in");});}
  var tel=document.getElementById("tel-link");
  if(tel){var t=cfg.phone.replace(/[^0-9+]/g,"");if(t){tel.href="tel:"+t;tel.textContent="전화하기 "+cfg.phone;tel.hidden=false;}else{tel.hidden=true;}}
})();

if("serviceWorker" in navigator&&location.protocol==="https:"){window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(){});});}

window.addEventListener("load",function(){setTimeout(function(){document.documentElement.classList.add("anim")},2500)});

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
