(function(){
"use strict";

// ---------------- config ----------------
var START_HOUR=6, END_HOUR=24, SLOT_MIN=30, SLOT_H=48;
var PX_PER_MIN=SLOT_H/SLOT_MIN;
var TOTAL_MIN=(END_HOUR-START_HOUR)*60, TOTAL_H=TOTAL_MIN*PX_PER_MIN;
var CATS=["업무","공부","개인","운동"];
var API="/api/events";

// ---------------- state ----------------
var db={version:2,events:{}};
var currentDate=new Date();
var monthCursor=new Date();
var selectedCategory="업무";
var draftForm=null;
var view="main";
var lastTickDay=null;

// ---------------- api ----------------
function apiLoad(){
  return fetch(API).then(function(r){return r.json();})
    .then(function(d){ db=d; });
}
function apiCreate(ev){
  return fetch(API,{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(ev)});
}
function apiPatch(date,id,patch){
  return fetch(API+"/"+date+"/"+id,{method:"PATCH",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(patch)});
}
function apiDelete(date,id){
  return fetch(API+"/"+date+"/"+id,{method:"DELETE"});
}
function reload(){ return apiLoad().then(render); }

// ---------------- helpers ----------------
function pad2(n){return (n<10?"0":"")+n;}
function dateKey(d){return d.getFullYear()+"-"+pad2(d.getMonth()+1)+"-"+pad2(d.getDate());}
function toMin(t){var p=t.split(":");return +p[0]*60 + +p[1];}
function toTimeStr(m){m=Math.max(0,Math.min(1439,Math.round(m)));
  return pad2(Math.floor(m/60))+":"+pad2(m%60);}
function fmtDuration(min){min=Math.round(min);
  var h=Math.floor(min/60),m=min%60;
  if(!h)return m+"분"; if(!m)return h+"시간"; return h+"시간 "+m+"분";}
var WEEKDAYS=["일","월","화","수","목","금","토"];
function fmtDateLabel(d){return (d.getMonth()+1)+"월 "+d.getDate()+"일 ("+WEEKDAYS[d.getDay()]+")";}
function dayList(d){return db.events[dateKey(d)]||[];}

var toastTimer=null;
function showToast(msg){
  var t=document.getElementById("toast");
  t.textContent=msg; t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer=setTimeout(function(){t.classList.remove("show");},1800);
}

// ---------------- view switch ----------------
function showMain(){ view="main";
  document.getElementById("mainView").classList.remove("hidden");
  document.getElementById("detailView").classList.add("hidden");
  render();
}
function showDetail(d){ view="detail";
  if(d) currentDate=new Date(d.getTime());
  document.getElementById("mainView").classList.add("hidden");
  document.getElementById("detailView").classList.remove("hidden");
  render();
}

// ---------------- render root ----------------
function render(){
  renderGlobalStats();
  if(view==="main"){ renderTodayCard(); renderWeekStrip(); renderMonth(); }
  else { renderDetailBar(); renderCategoryBar(); renderTimeline(); }
}

function renderGlobalStats(){
  var list=dayList(new Date()), total=0, done=0;
  list.forEach(function(ev){
    var d=Math.max(0,toMin(ev.end)-toMin(ev.start));
    total+=d; if(ev.done)done+=d;
  });
  document.getElementById("stats").innerHTML=
    "오늘 계획 <b>"+fmtDuration(total)+"</b> · 완료 <b>"+fmtDuration(done)+"</b>";
}

// ---------------- main: today card ----------------
function renderTodayCard(){
  var wrap=document.getElementById("todayList");
  wrap.innerHTML="";
  var list=dayList(new Date()).slice().sort(function(a,b){
    return toMin(a.start)-toMin(b.start);});
  if(!list.length){
    wrap.innerHTML='<div class="today-empty">오늘 일정이 없다. 일해라 김준태.</div>';
    return;
  }
  list.forEach(function(ev){
    var el=document.createElement("div");
    el.className="today-item"+(ev.done?" done":"");
    el.dataset.cat=ev.category;
    el.innerHTML='<span class="t-time">'+ev.start+"~"+ev.end+"</span>"+
      "<span>"+ev.title+"</span>";
    wrap.appendChild(el);
  });
}

// ---------------- main: week strip ----------------
function renderWeekStrip(){
  var wrap=document.getElementById("weekStrip");
  wrap.innerHTML="";
  var now=new Date();
  var sunday=new Date(now); sunday.setDate(now.getDate()-now.getDay());
  for(var i=0;i<7;i++){
    var d=new Date(sunday); d.setDate(sunday.getDate()+i);
    var cnt=dayList(d).length;
    var el=document.createElement("div");
    el.className="wd"+(dateKey(d)===dateKey(now)?" today":"");
    el.innerHTML='<div class="wd-name">'+WEEKDAYS[d.getDay()]+"</div>"+
      '<div class="wd-num">'+d.getDate()+"</div>"+
      '<div class="wd-cnt">'+(cnt?cnt+"건":"")+"</div>";
    (function(dd){ el.onclick=function(){showDetail(dd);}; })(d);
    wrap.appendChild(el);
  }
}

// ---------------- main: month calendar ----------------
function renderMonth(){
  var y=monthCursor.getFullYear(), m=monthCursor.getMonth();
  document.getElementById("monthLabel").textContent=y+"년 "+(m+1)+"월";
  var grid=document.getElementById("monthGrid");
  grid.innerHTML="";
  WEEKDAYS.forEach(function(w){
    var h=document.createElement("div");
    h.className="mg-head"; h.textContent=w; grid.appendChild(h);
  });
  var first=new Date(y,m,1);
  var cursor=new Date(y,m,1-first.getDay());
  var todayK=dateKey(new Date());
  for(var i=0;i<42;i++){
    var d=new Date(cursor.getTime());
    var cell=document.createElement("div");
    cell.className="mg-cell"+(d.getMonth()!==m?" other":"")+
      (dateKey(d)===todayK?" today":"");
    var dots="", seen={};
    dayList(d).forEach(function(ev){
      if(seen[ev.category])return; seen[ev.category]=1;
      dots+='<span class="mg-dot" style="background:var(--cat-'+ev.category+')"></span>';
    });
    cell.innerHTML=d.getDate()+'<div class="mg-dots">'+dots+"</div>";
    (function(dd){ cell.onclick=function(){showDetail(dd);}; })(d);
    grid.appendChild(cell);
    cursor.setDate(cursor.getDate()+1);
  }
}

// ---------------- detail: bar/category ----------------
function renderDetailBar(){
  document.getElementById("dateLabel").textContent=fmtDateLabel(currentDate);
  var list=dayList(currentDate), total=0, done=0;
  list.forEach(function(ev){
    var d=Math.max(0,toMin(ev.end)-toMin(ev.start));
    total+=d; if(ev.done)done+=d;
  });
  document.getElementById("dayStats").innerHTML=
    "계획 <b>"+fmtDuration(total)+"</b> · 완료 <b>"+fmtDuration(done)+"</b>";
}

function renderCategoryBar(){
  var bar=document.getElementById("categoryBar");
  bar.innerHTML="";
  CATS.forEach(function(cat){
    var btn=document.createElement("button");
    btn.className="cat-btn"+(cat===selectedCategory?" active":"");
    btn.dataset.cat=cat;
    btn.innerHTML='<span class="dot"></span>'+cat;
    btn.onclick=function(){selectedCategory=cat;renderCategoryBar();};
    bar.appendChild(btn);
  });
}

// ---------------- detail: timeline ----------------
function layoutDay(list){
  var sorted=list.slice().sort(function(a,b){
    return toMin(a.start)-toMin(b.start)||toMin(a.end)-toMin(b.end);});
  var clusters=[],cur=[],curEnd=-1;
  sorted.forEach(function(ev){
    var s=toMin(ev.start),e=toMin(ev.end);
    if(!cur.length||s<curEnd){cur.push(ev);curEnd=Math.max(curEnd,e);}
    else{clusters.push(cur);cur=[ev];curEnd=e;}
  });
  if(cur.length)clusters.push(cur);
  var out=[];
  clusters.forEach(function(cl){
    var ends=[],asg={};
    cl.forEach(function(ev){
      var s=toMin(ev.start),e=toMin(ev.end),ok=false;
      for(var c=0;c<ends.length;c++)
        if(ends[c]<=s){asg[ev.id]=c;ends[c]=e;ok=true;break;}
      if(!ok){asg[ev.id]=ends.length;ends.push(e);}
    });
    cl.forEach(function(ev){out.push({ev:ev,col:asg[ev.id],cols:ends.length});});
  });
  return out;
}

function renderTimeline(){
  var tl=document.getElementById("timeline");
  tl.innerHTML="";
  tl.style.height=(TOTAL_H+12)+"px";
  for(var i=0;i<=TOTAL_MIN;i+=SLOT_MIN){
    var isHour=i%60===0, top=6+i*PX_PER_MIN;
    var row=document.createElement("div");
    row.className="grid-row"+(isHour?" hour":"");
    row.style.top=top+"px"; tl.appendChild(row);
    if(isHour){
      var lb=document.createElement("div");
      lb.className="grid-label"; lb.style.top=top+"px";
      lb.textContent=pad2(START_HOUR+i/60)+":00"; tl.appendChild(lb);
    }
  }
  var track=document.createElement("div");
  track.className="track";
  track.style.height=TOTAL_H+"px"; track.style.marginTop="6px";
  track.addEventListener("click",onTrackClick);
  tl.appendChild(track);

  if(dateKey(currentDate)===dateKey(new Date())){
    var now=new Date();
    var nm=now.getHours()*60+now.getMinutes()-START_HOUR*60;
    if(nm>=0&&nm<=TOTAL_MIN){
      var nl=document.createElement("div");
      nl.className="now-line"; nl.style.top=(nm*PX_PER_MIN)+"px";
      track.appendChild(nl);
    }
  }
  layoutDay(dayList(currentDate)).forEach(function(it){
    track.appendChild(renderEventBlock(it.ev,it.col,it.cols));
  });
}

function renderEventBlock(ev,col,cols){
  var s=toMin(ev.start),e=toMin(ev.end);
  var top=(s-START_HOUR*60)*PX_PER_MIN;
  var h=Math.max(18,(e-s)*PX_PER_MIN);
  var w=100/cols, l=col*w;
  var k=dateKey(currentDate);

  var b=document.createElement("div");
  b.className="event-block"+(ev.done?" done":"");
  b.dataset.cat=ev.category;
  b.style.cssText="top:"+top+"px;height:"+h+"px;left:calc("+l+"% + 2px);width:calc("+w+"% - 4px)";

  var title=document.createElement("div");
  title.className="ev-title"; title.textContent=ev.title;
  b.appendChild(title);

  var tw=document.createElement("div"); tw.className="ev-time";
  var si=document.createElement("input"); si.type="time"; si.value=ev.start;
  var sep=document.createElement("span"); sep.textContent="~";
  var ei=document.createElement("input"); ei.type="time"; ei.value=ev.end;
  [si,ei].forEach(function(inp){inp.onclick=function(x){x.stopPropagation();};});
  si.onchange=function(){
    if(toMin(si.value)>=toMin(ev.end)){
      showToast("종료 시각이 시작 시각보다 빨라요"); reload(); return;
    }
    apiPatch(k,ev.id,{start:si.value}).then(reload);
  };
  ei.onchange=function(){
    if(toMin(ei.value)<=toMin(ev.start)){
      showToast("종료 시각이 시작 시각보다 빨라요"); reload(); return;
    }
    apiPatch(k,ev.id,{end:ei.value}).then(reload);
  };
  tw.appendChild(si); tw.appendChild(sep); tw.appendChild(ei);
  b.appendChild(tw);

  var del=document.createElement("button");
  del.className="del-btn"; del.textContent="\u00d7"; del.title="삭제";
  del.onclick=function(x){x.stopPropagation(); apiDelete(k,ev.id).then(reload);};
  b.appendChild(del);

  b.addEventListener("click",function(x){
    if(x.target.tagName==="INPUT"||x.target.closest(".del-btn"))return;
    apiPatch(k,ev.id,{done:!ev.done}).then(reload);
  });
  b.addEventListener("contextmenu",function(x){
    x.preventDefault(); apiDelete(k,ev.id).then(reload);
  });
  return b;
}

// ---------------- inline create ----------------
function onTrackClick(e){
  if(draftForm)return;
  var track=e.currentTarget;
  var rect=track.getBoundingClientRect();
  var clicked=START_HOUR*60+(e.clientY-rect.top)/PX_PER_MIN;
  var snapped=Math.round(clicked/SLOT_MIN)*SLOT_MIN;
  snapped=Math.max(START_HOUR*60,Math.min(END_HOUR*60-SLOT_MIN,snapped));
  openCreateForm(track,snapped);
}

function openCreateForm(track,startMin){
  var endMin=Math.min(END_HOUR*60-1,startMin+SLOT_MIN);
  var form=document.createElement("div");
  form.className="create-form";
  form.style.cssText="top:"+((startMin-START_HOUR*60)*PX_PER_MIN)+
    "px;height:"+Math.max(24,SLOT_MIN*PX_PER_MIN)+"px;left:2px;width:calc(100% - 4px)";
  form.style.borderColor="var(--cat-"+selectedCategory+")";

  var ti=document.createElement("input");
  ti.type="text"; ti.placeholder="제목 입력 후 Enter";
  var si=document.createElement("input"); si.type="time"; si.value=toTimeStr(startMin);
  var sep=document.createElement("span"); sep.textContent="~";
  var ei=document.createElement("input"); ei.type="time"; ei.value=toTimeStr(endMin);
  form.appendChild(ti);form.appendChild(si);form.appendChild(sep);form.appendChild(ei);
  track.appendChild(form);
  draftForm=form;
  ti.focus();

  function confirmForm(){
    if(draftForm!==form)return;              // 재진입 가드 (Enter+blur 이중실행 차단)
    var title=ti.value.trim();
    if(!title){cancelForm();return;}
    if(toMin(ei.value)<=toMin(si.value)){
      showToast("종료 시각이 시작 시각보다 빨라요");
      form.classList.add("flash");
      setTimeout(function(){form.classList.remove("flash");},500);
      return;
    }
    draftForm=null;                          // 소유권 즉시 해제 (v1 버그픽스)
    apiCreate({title:title,start:si.value,end:ei.value,
      category:selectedCategory,date:dateKey(currentDate)}).then(reload);
  }
  function cancelForm(){
    if(draftForm!==form)return;
    draftForm=null;
    if(form.parentNode)form.parentNode.removeChild(form);
  }
  [ti,si,ei].forEach(function(inp){
    inp.addEventListener("click",function(x){x.stopPropagation();});
    inp.addEventListener("keydown",function(x){
      if(x.key==="Enter"){x.preventDefault();confirmForm();}
      else if(x.key==="Escape"){x.preventDefault();cancelForm();}
    });
  });
  form.addEventListener("focusout",function(x){
    if(form.contains(x.relatedTarget))return;
    setTimeout(function(){
      if(draftForm!==form)return;
      if(ti.value.trim())confirmForm();else cancelForm();
    },0);
  });
}

// ---------------- nav ----------------
document.getElementById("todayCard").onclick=function(){showDetail(new Date());};
document.getElementById("backBtn").onclick=showMain;
document.getElementById("prevBtn").onclick=function(){
  currentDate.setDate(currentDate.getDate()-1);render();};
document.getElementById("nextBtn").onclick=function(){
  currentDate.setDate(currentDate.getDate()+1);render();};
document.getElementById("todayBtn").onclick=function(){
  currentDate=new Date();render();};
document.getElementById("monthPrev").onclick=function(){
  monthCursor.setMonth(monthCursor.getMonth()-1);renderMonth();};
document.getElementById("monthNext").onclick=function(){
  monthCursor.setMonth(monthCursor.getMonth()+1);renderMonth();};

// ---------------- ticks (자정 넘김 대응 - v1 버그픽스) ----------------
lastTickDay=dateKey(new Date());
setInterval(function(){
  var tk=dateKey(new Date());
  if(tk!==lastTickDay){
    if(dateKey(currentDate)===lastTickDay)currentDate=new Date();
    lastTickDay=tk; render(); return;
  }
  if(!draftForm&&view==="detail")renderTimeline();
},60000);

// ---------------- boot ----------------
reload();
})();
