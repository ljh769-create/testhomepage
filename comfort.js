// 위로 기능: 숨 고르기 안내, 오늘 마음 고르기, 야간 모드. 개인 정보는 저장하거나 전송하지 않습니다.
(function(){
  var root=document.documentElement;
  var reduce=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- 야간 모드 ----
  function setNight(on){
    root.classList.toggle("night",on);
    try{localStorage.setItem("gd-night",on?"1":"0");}catch(e){}
    var b=document.querySelector(".nightbtn");
    if(b){b.setAttribute("aria-pressed",on);b.textContent=on?"낮 모드":"밤 모드";}
  }
  var menu=document.querySelector(".menubar")||document.querySelector(".menu");
  if(menu){
    var nb=document.createElement("button");
    nb.type="button";nb.className="nightbtn";nb.setAttribute("aria-pressed","false");nb.textContent="밤 모드";
    nb.addEventListener("click",function(){setNight(!root.classList.contains("night"));});
    menu.appendChild(nb);
  }

  // ---- 펼침 메뉴 ----
  var toggles=document.querySelectorAll(".menu .has");
  function closeAll(except){
    toggles.forEach(function(t){
      var p=document.getElementById(t.getAttribute("data-panel"));
      if(t!==except){t.setAttribute("aria-expanded","false");if(p)p.hidden=true;}
    });
  }
  toggles.forEach(function(t){
    t.addEventListener("click",function(e){
      e.stopPropagation();
      var p=document.getElementById(t.getAttribute("data-panel"));if(!p)return;
      var open=p.hidden;closeAll(t);
      p.hidden=!open;t.setAttribute("aria-expanded",open);
    });
  });
  document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".menu"))closeAll(null);});
  document.addEventListener("keydown",function(e){if(e.key==="Escape")closeAll(null);});
  document.querySelectorAll(".panel a").forEach(function(a){a.addEventListener("click",function(){closeAll(null);});});
  var saved=null;try{saved=localStorage.getItem("gd-night");}catch(e){}
  if(saved==="1")setNight(true);

  // ---- 숨 고르기 (4초 들이쉬고 6초 내쉬기) ----
  document.querySelectorAll(".breath").forEach(function(box){
    var label=box.querySelector(".breath-label");
    var circle=box.querySelector(".breath-circle");
    if(!label||!circle)return;
    if(reduce){label.textContent="4초 들이쉬고, 6초 내쉬어 보세요";return;}
    var inhale=true,timer=null;
    function step(){
      if(document.body.classList.contains("paused")){label.textContent="멈춰 있습니다";timer=setTimeout(step,1000);return;}
      if(inhale){
        label.textContent="천천히 들이쉬세요";
        circle.style.transition="transform 4s ease-in-out";circle.style.transform="scale(1.35)";
        timer=setTimeout(function(){inhale=false;step();},4000);
      }else{
        label.textContent="길게 내쉬세요";
        circle.style.transition="transform 6s ease-in-out";circle.style.transform="scale(0.8)";
        timer=setTimeout(function(){inhale=true;step();},6000);
      }
    }
    step();
  });

  // ---- 오늘 마음 고르기 ----
  var out=document.getElementById("mood-out");
  var MSG={
    sleep:{t:"잠이 오지 않는 밤은 누구에게나 있습니다.",b:"잠이 안 오는 것은 의지가 약해서가 아닙니다. 오늘은 억지로 자려고 하기보다 눈을 감고 숨만 따라가 보세요.",h:"sleep.html",l:"불면·수면 안내 보기"},
    appetite:{t:"먹는 것으로 마음을 달래는 날도 있습니다.",b:"자신을 탓하지 않으셔도 됩니다. 언제, 어떤 마음일 때 입이 당기는지만 알아도 시작입니다.",h:"diet.html",l:"대사·식욕 안내 보기"},
    pain:{t:"아픈 몸으로 하루를 버티셨군요.",b:"어떤 동작에서 가장 불편한지만 기억해 오세요. 이야기는 이어서 듣겠습니다.",h:"#chuna",l:"추나·통증 안내 보기"},
    tired:{t:"많이 지치셨군요.",b:"쉬지 못하고 달려오신 것 같습니다. 오늘은 잘하려고 하지 않으셔도 됩니다. 마음이 많이 힘드시면 혼자 견디지 마시고 정신건강 위기상담 전화 109(24시간)에 연락하세요.",h:"guide/mental/burnout-exhaustion.html",l:"지칠 때 읽는 글"},
    ok:{t:"다행입니다.",b:"오늘 편안했던 순간을 하나만 기억해 두세요. 그 순간이 내일의 리듬이 됩니다.",h:null,l:null}
  };
  document.querySelectorAll("[data-mood]").forEach(function(btn){
    btn.addEventListener("click",function(){
      var m=MSG[btn.getAttribute("data-mood")];if(!m||!out)return;
      document.querySelectorAll("[data-mood]").forEach(function(x){x.setAttribute("aria-pressed",x===btn);});
      out.innerHTML="";
      var p1=document.createElement("p");p1.className="moodtitle";p1.textContent=m.t;
      var p2=document.createElement("p");p2.textContent=m.b;
      out.appendChild(p1);out.appendChild(p2);
      if(m.h){var a=document.createElement("a");a.className="btn";a.href=m.h;a.textContent=m.l;out.appendChild(a);}
      out.hidden=false;
    });
  });
})();

// 내부 링크 위치 기록(GA4): UTM 대신 data-link-location 속성을 internal_link_click 이벤트의 link_location으로 보낸다.
// 내부 링크에 UTM을 붙이면 GA4가 새 세션을 만들고 실제 유입 경로(네이버 검색·블로그 등)를 덮어쓰므로 금지.
(function(){
  if(window.__navTrack)return;window.__navTrack=1;
  document.addEventListener("click",function(e){
    var a=e.target.closest&&e.target.closest("a[data-link-location]");if(!a)return;
    var h=a.getAttribute("href")||"";if(/^(https?:)?\/\//i.test(h)&&h.indexOf(location.host)<0)return;
    if(/booking\.naver\.com|pf\.kakao\.com|^tel:/i.test(h))return;
    var p={link_location:a.getAttribute("data-link-location"),link_text:(a.textContent||"").trim().slice(0,40),link_url:h.slice(0,100),page_path:location.pathname};
    if(typeof window.gtag==="function")window.gtag("event","internal_link_click",p);
  },true);
})();

// 예약·상담 버튼 클릭 기록(GA4): 네이버 예약 → booking_click, 카카오톡 → kakao_click, 전화 → call_click.
// 어느 글의 어느 자리(위·중간·아래·하단 고정 바·머리글)에서 눌렀는지 함께 남긴다. 개인 정보는 보내지 않는다.
(function(){
  if(window.__ctaTrack)return;window.__ctaTrack=1;
  function kind(h){
    if(/booking\.naver\.com/.test(h))return "booking_click";
    if(/pf\.kakao\.com/.test(h))return "kakao_click";
    if(/^tel:/i.test(h))return "call_click";
    return "";
  }
  function where(a){
    var d=a.closest("[data-cta]");if(d)return d.getAttribute("data-cta");
    if(a.closest(".actbar"))return "bar";
    if(a.closest("header"))return "header";
    if(a.closest("footer"))return "footer";
    if(a.closest("article"))return "article";
    return "page";
  }
  document.addEventListener("click",function(e){
    var a=e.target.closest&&e.target.closest("a[href]");if(!a)return;
    var ev=kind(a.getAttribute("href")||"");if(!ev)return;
    var m=location.pathname.match(/\/guide\/([^\/]+)\/([^\/]+)\.html$/);
    var p={cta_position:where(a),link_location:a.getAttribute("data-link-location")||where(a),link_text:(a.textContent||"").trim().slice(0,40),
      post_category:m?m[1]:"",post_slug:m?m[2]:"",page_path:location.pathname};
    if(typeof window.gtag==="function")window.gtag("event",ev,p);
    else{window.dataLayer=window.dataLayer||[];(function(){window.dataLayer.push(arguments);})("event",ev,p);}
  },true);
})();
