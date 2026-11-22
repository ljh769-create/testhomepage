// 글 페이지용 경량 스크립트: 전화 링크 설정(config.js 없이 site 기본값 사용)과 스크롤 등장 효과
(function(){
  var rv=document.querySelectorAll(".reveal");
  if("IntersectionObserver" in window){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target);}});},{threshold:.12});
    rv.forEach(function(el){io.observe(el);});
  }else{rv.forEach(function(el){el.classList.add("in");});}
})();
