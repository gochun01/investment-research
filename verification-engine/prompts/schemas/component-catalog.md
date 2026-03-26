# Verification Report HTML — 컴포넌트 카탈로그

모든 CSS 컴포넌트의 정확한 마크업과 CSS. 새 리포트 생성 시 이 카탈로그에서 조합한다.

---

## 1. CSS Variables (Light + Dark)

```css
:root,[data-theme="light"]{
  --bg:#fafaf8;--surface:#fff;--card:#f5f5f2;
  --navy:#1B2A4A;--darkBlue:#2C5697;--blue:#4472C4;
  --lightBlue:#D6E4F0;--paleBlue:#EDF2F9;
  --text:#1a1a1a;--sub:#4a4a4a;--dim:#8a8a8a;
  --border:#d8d8d4;--red:#c0392b;--green:#1a7a4c;--gold:#b8860b;--line:#e2e2de;
  --topbar-bg:#1B2A4A;--topbar-text:#fff;--topbar-dim:#8ea8cc;
  --exec-bg:#EDF2F9;--key-bg:#fdf6ec;--key-text:#5a4a20;
  --alert-bg:#fef2f2;--alert-text:#6b2020;
  --tag-bull-bg:#e8f5e9;--tag-bear-bg:#fef2f2;--tag-caution-bg:#fff8e1;
  --nav-bg:rgba(255,255,255,.92);--shadow:rgba(27,42,74,.06)
}
[data-theme="dark"]{
  --bg:#0d1117;--surface:#161b22;--card:#1c2128;
  --navy:#c9d1d9;--darkBlue:#58a6ff;--blue:#79c0ff;
  --lightBlue:#1f3a5f;--paleBlue:#131d2b;
  --text:#e6edf3;--sub:#b1bac4;--dim:#6e7681;
  --border:#30363d;--red:#f85149;--green:#3fb950;--gold:#d29922;--line:#21262d;
  --topbar-bg:#010409;--topbar-text:#e6edf3;--topbar-dim:#6e7681;
  --exec-bg:#131d2b;--key-bg:#1c1a10;--key-text:#d29922;
  --alert-bg:#1a0e0e;--alert-text:#f85149;
  --tag-bull-bg:#0d2818;--tag-bear-bg:#1a0e0e;--tag-caution-bg:#1c1a10;
  --nav-bg:rgba(13,17,23,.95);--shadow:rgba(0,0,0,.3)
}
```

---

## 2. Top Bar (sticky)

```html
<header class="topbar"><div class="topbar-inner">
  <div class="topbar-brand">6-Layer Verification Engine</div>
  <div class="topbar-right">
    <div class="topbar-division">Document Verification · v1.2</div>
    <button class="ctrl-btn" id="viewToggle">SHORT</button>
    <button class="ctrl-btn" id="themeToggle">◐ DARK</button>
    <button class="ctrl-btn" id="printBtn">⎙ PRINT</button>
  </div>
</div></header>
```

```css
.topbar{background:var(--topbar-bg);padding:14px 0;position:sticky;top:0;z-index:100}
.topbar-inner{max-width:780px;margin:0 auto;padding:0 32px;display:flex;justify-content:space-between;align-items:center}
.topbar-brand{font-family:'Libre Baskerville',serif;font-size:15px;font-weight:700;color:var(--topbar-text)}
.topbar-right{display:flex;align-items:center;gap:10px}
.topbar-division{font-size:12px;color:var(--topbar-dim)}
.ctrl-btn{background:none;border:1px solid rgba(255,255,255,.2);color:var(--topbar-text);font-size:11px;font-weight:600;padding:4px 11px;border-radius:3px;cursor:pointer;transition:all .2s;font-family:'DM Sans',sans-serif}
.ctrl-btn:hover{border-color:rgba(255,255,255,.5);background:rgba(255,255,255,.08)}
.ctrl-btn.active{background:rgba(255,255,255,.15)}
```

---

## 3. Float Nav (우측 고정 INDEX)

**⚠️ `<a>` 태그 사용 금지 (V-13).** `<div class="nav-item">` + `data-target` 사용.

```html
<nav class="float-nav">
  <div class="float-nav-title">CONTENTS</div>
  <div class="nav-item" data-target="s1">I. Summary</div>
  <div class="nav-item" data-target="s2">II. 6-Layer 판정</div>
  <div class="nav-item" data-target="s3">III. Findings</div>
  <div class="nav-item" data-target="s4">IV. Fact Check</div>
  <div class="nav-item" data-target="s5">V. Logic &amp; KC</div>
  <div class="nav-item" data-target="s6">VI. Omission</div>
  <div class="nav-item" data-target="s7">VII. 수정 대시보드</div>
</nav>
```

```css
.float-nav{position:fixed;right:16px;top:70px;width:172px;background:var(--nav-bg);border:1px solid var(--border);border-radius:6px;padding:14px 16px;z-index:90;box-shadow:0 2px 12px var(--shadow);max-height:calc(100vh - 100px);overflow-y:auto}
.float-nav-title{font-family:'DM Mono',monospace;font-size:10px;color:var(--dim);letter-spacing:2px;margin-bottom:10px}
.float-nav .nav-item{display:block;font-size:11.5px;color:var(--dim);cursor:pointer;padding:4px 0 4px 10px;border-left:2px solid transparent;transition:all .2s;line-height:1.4}
.float-nav .nav-item:hover{color:var(--darkBlue)}
.float-nav .nav-item.active{color:var(--darkBlue);border-left-color:var(--darkBlue);font-weight:600}
```

JS:
```javascript
document.querySelectorAll('.nav-item').forEach(function(d){
  d.addEventListener('click',function(){
    var el=document.getElementById(this.getAttribute('data-target'));
    if(el)el.scrollIntoView({behavior:'smooth',block:'start'});
  });
});
var secs=document.querySelectorAll('.section[id]'),navs=document.querySelectorAll('.nav-item');
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){navs.forEach(function(l){l.classList.remove('active')});var t=e.target.id;navs.forEach(function(n){if(n.getAttribute('data-target')===t)n.classList.add('active')})}})},{rootMargin:'-20% 0px -70% 0px'});secs.forEach(function(s){io.observe(s)})}
```

---

## 4. Short Notice + Full-Only

```html
<div class="short-notice">📋 요약 모드 — I · III · VII만 표시. <strong>FULL</strong>로 전체 보기</div>
```

```css
.short-notice{display:none;background:var(--paleBlue);border:1px dashed var(--darkBlue);border-radius:6px;padding:14px 20px;margin:16px 0;font-size:13px;color:var(--darkBlue);text-align:center}
body.short-mode .short-notice{display:block}
.section.full-only{display:block}
body.short-mode .section.full-only{display:none}
```

---

## 5. Highlight Boxes

```css
.exec-box{background:var(--exec-bg);border-left:4px solid var(--darkBlue);padding:24px 28px;margin:20px 0;border-radius:0 6px 6px 0}
.exec-box p{font-size:14.5px;color:var(--navy);margin-bottom:10px}
.exec-box p:last-child{margin-bottom:0}
.exec-label{font-size:11px;font-weight:700;letter-spacing:2px;color:var(--darkBlue);margin-bottom:8px}
.key-finding{background:var(--key-bg);border-left:4px solid var(--gold);padding:24px 28px;margin:20px 0;border-radius:0 6px 6px 0}
.key-finding p{color:var(--key-text)}
.alert-box{background:var(--alert-bg);border-left:4px solid var(--red);padding:24px 28px;margin:20px 0;border-radius:0 6px 6px 0}
.alert-box p{color:var(--alert-text)}
```

---

## 6. Finding Card (핵심 컴포넌트)

### 마크업 (3변형)

**f-red + definitive** (🔴 확정):
```html
<div class="finding-card f-red">
  <div class="finding-header">
    <div class="finding-id">F-001</div>
    <div><span class="v r">L1 FACT 🔴</span></div>
  </div>
  <div class="finding-row"><span class="finding-label">📍</span> 위치</div>
  <div class="finding-row"><span class="finding-label">📝</span> 원문</div>
  <div class="finding-row"><span class="finding-label">🏷️</span> error_type</div>
  <div class="finding-row"><span class="finding-label">📊</span> 근거</div>
  <div class="finding-fix">
    <div class="finding-fix-header definitive">✏️ 수정 [확정]</div>
    "원본" → "수정값 (출처, 날짜)"
  </div>
  <div class="finding-impact">💡 수정 시: L1 🔴 → 🟢</div>
</div>
```

**f-gold + recommended** (🟡 권장):
- `.finding-card.f-gold` + `.finding-fix-header.recommended`
- fix 내용: 방향 + 예시

**f-blue + advisory** (⚠️ 경고):
- `.finding-card.f-blue` + `.finding-fix-header.advisory`
- fix 내용: warning + implication

### CSS

```css
.finding-card{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:20px 24px;margin:14px 0;position:relative}
.finding-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:6px 0 0 6px}
.finding-card.f-red::before{background:var(--red)}
.finding-card.f-gold::before{background:var(--gold)}
.finding-card.f-blue::before{background:var(--darkBlue)}
.finding-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px}
.finding-id{font-family:'DM Mono',monospace;font-size:12px;font-weight:700;color:var(--navy)}
.finding-row{display:flex;gap:8px;margin-bottom:6px;font-size:13px;color:var(--sub);line-height:1.6}
.finding-label{font-size:11px;min-width:20px;flex-shrink:0}
.finding-fix{background:var(--card);border-radius:4px;padding:12px 16px;margin-top:10px;font-size:13px;color:var(--sub);line-height:1.7}
.finding-fix-header{font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:6px}
.finding-fix-header.definitive{color:var(--green)}
.finding-fix-header.recommended{color:var(--gold)}
.finding-fix-header.advisory{color:var(--red)}
.finding-impact{font-family:'DM Mono',monospace;font-size:12px;margin-top:8px;padding:6px 12px;background:var(--paleBlue);border-radius:3px;color:var(--darkBlue);display:inline-block}
```

---

## 7. Verdict Badge

```css
.v{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:3px;vertical-align:middle}
.v.g{background:var(--tag-bull-bg);color:var(--green)}
.v.y{background:var(--tag-caution-bg);color:var(--gold)}
.v.r{background:var(--tag-bear-bg);color:var(--red)}
.v.k{background:var(--card);color:var(--dim)}
```

---

## 8. Channel Card (Fact Check용, 클릭 확장)

```css
.channel-grid{display:grid;gap:14px;margin:20px 0}
.channel-card{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:20px 24px;cursor:pointer;transition:all .2s;position:relative}
.channel-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:6px 0 0 6px}
.channel-card.ch-green::before{background:var(--green)}
.channel-card.ch-gold::before{background:var(--gold)}
.channel-card.ch-red::before{background:var(--red)}
.channel-card.ch-blue::before{background:var(--darkBlue)}
.channel-card:hover{border-color:var(--darkBlue);box-shadow:0 2px 8px var(--shadow)}
.ch-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px}
.ch-name{font-size:15px;font-weight:700;color:var(--navy)}
.ch-tags{display:flex;gap:6px}
.ch-tag{font-size:10px;font-weight:600;padding:3px 10px;border-radius:3px}
.ch-tag.verified{background:var(--tag-bull-bg);color:var(--green)}
.ch-tag.med{background:var(--tag-caution-bg);color:var(--gold)}
.ch-tag.high{background:var(--tag-bear-bg);color:var(--red)}
.ch-chain{font-family:'DM Mono',monospace;font-size:12.5px;color:var(--sub);background:var(--card);padding:12px 16px;border-radius:4px;margin:10px 0;line-height:1.7}
.ch-chain .ar{color:var(--darkBlue);font-weight:600}
.ch-chain .neg{color:var(--red);font-weight:600}
.ch-chain .pos{color:var(--green);font-weight:600}
.ch-detail{max-height:0;overflow:hidden;transition:max-height .5s ease;font-size:13.5px;color:var(--sub);line-height:1.8}
.channel-card.open .ch-detail{max-height:1200px;padding-top:12px}
.ch-precedent{background:var(--card);border-left:2px solid var(--gold);padding:10px 14px;margin:10px 0;font-size:12.5px;border-radius:0 4px 4px 0}
.ch-precedent strong{color:var(--gold)}
.ch-expand{font-size:11px;color:var(--dim);margin-top:6px}
.channel-card.open .ch-expand{display:none}
```

---

## 9. Tables

```css
.table-wrap{overflow-x:auto;margin:16px 0}
.monitor-table{width:100%;border-collapse:collapse;font-size:13px;min-width:480px}
.monitor-table th{background:var(--topbar-bg);color:var(--topbar-text);padding:8px 14px;text-align:left;font-weight:600;font-size:11px;letter-spacing:1px}
.monitor-table td{padding:8px 14px;border-bottom:1px solid var(--line);font-family:'DM Mono',monospace;font-size:12.5px;color:var(--sub)}
.monitor-table tr:nth-child(even) td{background:var(--card)}
.val-current{font-weight:700;color:var(--navy)}
.val-warn{color:var(--gold)}
.val-alert{color:var(--red);font-weight:600}
```

---

## 10. Scenario Grid

```css
.scenario-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}
.scenario-card{background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:18px 14px;text-align:center}
.scenario-name{font-size:13px;font-weight:700;margin-bottom:10px}
.scenario-krw{font-family:'DM Mono',monospace;font-size:20px;font-weight:700;margin-bottom:4px}
.scenario-desc{font-size:11.5px;color:var(--sub);margin-bottom:10px;line-height:1.5}
```

---

## 11. Responsive + Print

```css
@media(max-width:700px){
  .page{padding:0 16px}.report-title{font-size:22px}
  .topbar-division{display:none}.scenario-grid{grid-template-columns:1fr}
  .float-nav{right:8px;width:140px;padding:10px 12px}
  .float-nav .nav-item{font-size:10.5px}
}
@media print{
  .topbar,.float-nav,.ctrl-btn,.short-notice{display:none!important}
  .channel-card .ch-detail{max-height:none!important;padding-top:12px!important}
  .ch-expand{display:none!important}body{font-size:12px}
  .section.full-only{display:block!important}
  .tip{border-bottom:none!important}
  .tip::after{display:none!important}
}
```

---

## 12. Tooltip (용어 주석)

영어 약자, 전문용어에 마우스를 올리면 설명이 표시된다.

### 마크업

```html
<span class="tip" data-tip="Kill Condition — 이 전제가 거짓이면 결론이 무너지는 조건">KC</span>
<span class="tip" data-tip="Bridging·Begging·Jumping — 논증 오류 3유형">BBJ Break</span>
<span class="tip" data-tip="MCP 1차 소스 직접 확인">VERIFIED</span>
```

### CSS

```css
.tip{position:relative;border-bottom:1.5px dotted var(--darkBlue);cursor:help;font-weight:600}
.tip::after{
  content:attr(data-tip);
  position:absolute;bottom:calc(100% + 6px);left:50%;transform:translateX(-50%);
  background:var(--topbar-bg);color:var(--topbar-text);
  font-size:12px;font-weight:400;line-height:1.5;
  padding:8px 14px;border-radius:5px;white-space:normal;width:max-content;max-width:280px;
  opacity:0;visibility:hidden;transition:opacity .2s,visibility .2s;
  z-index:200;pointer-events:none;
  box-shadow:0 4px 12px rgba(0,0,0,.15);
}
.tip::before{
  content:'';position:absolute;bottom:calc(100% + 2px);left:50%;transform:translateX(-50%);
  border:5px solid transparent;border-top-color:var(--topbar-bg);
  opacity:0;visibility:hidden;transition:opacity .2s,visibility .2s;
  z-index:201;pointer-events:none;
}
.tip:hover::after,.tip:hover::before{opacity:1;visibility:visible}
```

### 사용 규칙

1. **최소한으로 부착.** 일반 독자가 맥락에서 추론 불가능한 전문용어에만 부착. 과잉 부착 금지.
2. **부착 기준**: 해당 분야 비전문가가 검색 없이 의미를 알 수 없는 용어 (예: KC, BBJ, 심리불속행, say on pay, 섀도보팅)
3. **부착하지 않는 용어**: 맥락에서 뜻이 명확한 용어 (DART, MCP, LLM 등), 범용 약어, 회사명, 기사에서 이미 설명한 용어
4. **같은 용어는 문서 내 최초 1회만** 부착. 이후 반복은 일반 텍스트.
5. **data-tip 형식**: "영문 풀네임 — 한줄 한글 설명"
