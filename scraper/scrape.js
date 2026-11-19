// 나이스캐치 강서리그 수집기 — Claude 내장 브라우저(nicecatch.kr 페이지)에서 실행
// 사용: await GS.list()  → 일정·결과 목록 수집
//       await GS.boxes(n) → 아직 안 읽은 경기 상세기록을 최대 n개 수집
//       GS.save(year)     → gangseo_<year>.json 다운로드
window.GS = window.GS || { sched: [], results: [], games: {}, year: null };
(function () {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const go = async (path) => {
    history.pushState({}, '', path);
    window.dispatchEvent(new PopStateEvent('popstate', { state: {} }));
  };
  const lines = () => document.body.innerText.split('\n').map(s => s.trim()).filter(Boolean);

  GS.setYear = async function (year) {
    const sel = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.text === year + '년'));
    const opt = [...sel.options].find(o => o.text === year + '년');
    if (sel.value !== opt.value) { sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait(3000); }
    GS.year = year; GS.seasonId = opt.value;
  };

  GS.list = async function () {
    // 1) 전체 경기일정
    await go('/league/gangseo/schedule'); await wait(3500);
    let sel = document.getElementById('leagueSelectBox');
    if (sel && sel.value !== '') { sel.value = ''; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait(3000); }
    const L = lines(); let date = null; const sched = [];
    for (let i = 0; i < L.length; i++) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(L[i])) date = L[i];
      if (L[i] === 'VS' && date) {
        sched.push({ d: date, t: L[i - 2], a: L[i - 1], b: L[i + 1], lg: L[i + 2], v: L[i + 3] });
      }
    }
    GS.sched = sched;
    // 2) 전체 경기결과
    await go('/league/gangseo/game/score'); await wait(3500);
    sel = document.getElementById('leagueSelectBox');
    if (sel && sel.value !== '') { sel.value = ''; sel.dispatchEvent(new Event('change', { bubbles: true })); await wait(3000); }
    const res = [];
    for (const a of [...document.querySelectorAll('a')].filter(a => /상세결과/.test(a.textContent))) {
      const row = a.parentElement.parentElement;
      const c = [...row.children].map(x => x.innerText.trim().replace(/\s+/g, ' '));
      const blk = a.closest('.widget-item');
      const d = blk ? blk.firstElementChild.innerText.trim() : null;
      const href = a.getAttribute('href'); const p = href.split('/');
      res.push({ d, t: c[0], a: c[1], sc: c[2], b: c[3], lg: c[4], lid: p[p.length - 2], gid: p[p.length - 1] });
    }
    GS.results = res;
    return { sched: sched.length, results: res.length };
  };

  const parseBox = () => {
    const box = document.querySelector('.widget-item.result');
    const mb = box.querySelector('.widget-match-box2');
    const head = mb.children[0].innerText.replace(/\s+/g, ' ').trim();
    const teams = [...mb.children[1].children].map(tb => tb.innerText.replace(/\s+/g, ' ').trim());
    const md = document.querySelector('.match-rounds > div');
    const rounds = md && md.children[1] ? [...md.children[1].children]
      .map(r => [...(r.children[1] ? r.children[1].children : [])].map(x => x.textContent.trim())) : [];
    const tbs = [...document.querySelectorAll('table')];
    const rows = t => t ? [...t.querySelectorAll('tr')].map(r => [...r.children].map(c => c.innerText.trim().replace(/\s+/g, ' '))) : [];
    return { head, teams, rounds, t: tbs.map(rows) };
  };

  GS.boxes = async function (n) {
    let done = 0, prev = '';
    const t0 = document.querySelector('table'); prev = t0 ? t0.innerText.slice(0, 300) : '';
    for (const g of GS.results) {
      if (GS.games[g.gid] || done >= n) continue;
      await go(`/league/gangseo/game/score/${g.lid}/${g.gid}`);
      let ok = false;
      for (let i = 0; i < 30; i++) {
        await wait(400);
        const t = document.querySelector('table');
        const s = t ? t.innerText.slice(0, 300) : '';
        const m = document.querySelector('.widget-match-box2');
        if (t && m && s !== prev && m.innerText.includes(g.a)) { ok = true; break; }
      }
      await wait(700);
      const t = document.querySelector('table'); prev = t ? t.innerText.slice(0, 300) : '';
      try { GS.games[g.gid] = Object.assign({ ok }, parseBox()); } catch (e) { GS.games[g.gid] = { ok: false, err: String(e) }; }
      done++;
    }
    return { done, total: Object.keys(GS.games).length, of: GS.results.length };
  };

  GS.save = function (year) {
    const out = { year: year || GS.year, seasonId: GS.seasonId, at: new Date().toISOString(), sched: GS.sched, results: GS.results, games: GS.games };
    const b = new Blob([JSON.stringify(out)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(b);
    a.download = `gangseo_${out.year}.json`; document.body.appendChild(a); a.click(); a.remove();
    return b.size;
  };
})();
