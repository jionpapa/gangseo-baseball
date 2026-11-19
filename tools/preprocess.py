"""나이스캐치 수집 원자료(gangseo_<연도>.json) → 앱용 데이터(data/season_<연도>.json)

타석마다 결과 코드를 만들고, 상대 투수 배정까지 미리 계산해 둔다.
타석 코드: "결과:방향" 형식
  결과  1B 2B 3B HR(안타) / GO 땅볼아웃 FO 뜬공아웃 LO 직선타아웃 / E 실책출루 / FC 야수선택
        SF 희생플라이 SH 희생번트 / K 삼진 BB 볼넷 HBP 사구 / INT 타격방해 / OUT 기타 아웃
  방향  L LC C RC R(외야) / P3 PS P1 P2 P4 P5(3루·유격·투수·포수·2루·1루) / U(불명)
  안타가 내야안타면 IH 표시: 1B:PS:IH 처럼 셋째 칸
"""
import json
import re
import sys

SKIP = re.compile(r'^(\d타점|도루|도루사|득점|실책진루|주루사|주자아웃|포일|폭투|대주자|견제사.*|보크|타구맞음|리터치.*|어필.*)$')


def strip_paren(s):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'\([^()]*\)', ' ', s)
    return s


def clean_name(raw):
    raw = raw.replace(' ', '')
    m = re.search(r'\(([^()]*)\)$', raw)
    num = m.group(1).replace('번', '') if m else ''
    name = strip_paren(raw).strip()
    if re.fullmatch(r'\d{6,}', name):  # 이름 대신 긴 숫자(개인식별번호로 보이는 값)는 감춘다
        name = '이름미표기'
    return f'{name}({num})' if num else name


def direction(t):
    for pre, d in (('좌중', 'LC'), ('우중', 'RC'), ('좌', 'L'), ('중', 'C'), ('우', 'R'),
                   ('三', 'P3'), ('유', 'PS'), ('투', 'P1'), ('포', 'P2'), ('二', 'P4'), ('一', 'P5')):
        if t.startswith(pre):
            return d
    return 'U'


def code_of(t):
    """타석 결과 토큰 하나 → 코드 (주루 기록이면 None)"""
    if not t or SKIP.match(t):
        return None
    if t in ('4구', '고4', '고의4구', '고의사구'):
        return 'BB'
    if t == '사구':
        return 'HBP'
    if t.startswith('삼진') or t.startswith('낫아웃'):
        return 'K'
    if t == '타격방해':
        return 'INT'
    if t in ('수비방해', '부정위'):
        return 'OUT'
    if t == '야수선택':
        return 'FC:U'
    d = direction(t)
    if re.search(r'희플(진루)?$', t):
        return f'SF:{d}'
    if re.search(r'희(타|번)(진루)?$', t):
        return f'SH:{d}'
    m = re.search(r'(안|2|3|홈)$', t)
    if m:
        kind = {'안': '1B', '2': '2B', '3': '3B', '홈': 'HR'}[m.group(1)]
        ih = ':IH' if '내안' in t else ''
        return f'{kind}:{d}{ih}'
    if re.search(r'(땅|땅진루|병)$', t):
        return f'GO:{d}'
    if re.search(r'(플|파플|인필)$', t):
        return f'FO:{d}'
    if t.endswith('직'):
        return f'LO:{d}'
    if t.endswith('실'):
        return f'E:{d}'
    return f'OUT:{d}'


def cell_codes(cell):
    out = []
    for t in re.split(r'\s*/\s*|\s+', strip_paren(cell)):
        c = code_of(t)
        if c:
            out.append(c)
    return out


def to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def parse_bat(rows):
    """타자 표 → [{slot,name,pos,inn:[[codes]...],box:{...}}]"""
    if not rows:
        return []
    hdr = rows[0]
    i_pos, i_avg = hdr.index('포지션'), hdr.index('타율')
    names = hdr[i_avg + 1:]
    keymap = {'타수': 'ab', '안타': 'h', '루타': 'tb', '타점': 'rbi', '득점': 'r', '도루': 'sb', '도루자': 'cs',
              '희타': 'sh', '희플': 'sf', '4구': 'bb', '死구': 'hbp', '삼진': 'k', '병살': 'gdp'}
    out, slot = [], 0
    for r in rows[1:]:
        if len(r) < len(hdr) or '합' in r[1] or not r[1].strip():
            continue
        s = r[0].strip()
        if s.isdigit():
            slot = int(s)
        box = {keymap[n]: to_int(v) for n, v in zip(names, r[i_avg + 1:]) if n in keymap}
        out.append({'slot': slot, 'name': clean_name(r[1]), 'pos': r[i_pos],
                    'inn': [cell_codes(c) for c in r[i_pos + 1:i_avg]], 'box': box})
    return out


def parse_pit(rows):
    if not rows:
        return []
    hdr = rows[0]
    keymap = {'승패': 'dec', '이닝': 'ip', '타자': 'bf', '타수': 'ab', '안타': 'h', '홈런': 'hr', '희타/희플': 'sac',
              '4구': 'bb', '死구': 'hbp', '삼진': 'k', '폭투': 'wp', '보크': 'bk', '실점': 'r', '자책점': 'er'}
    out = []
    for r in rows[1:]:
        if len(r) < len(hdr) or '합' in r[1] or not r[1]:
            continue
        p = {'name': clean_name(r[1])}
        for n, v in zip(hdr, r):
            if n in keymap:
                p[keymap[n]] = v if keymap[n] in ('dec', 'ip') else to_int(v)
        out.append(p)
    return out


def pa_sequence(bat):
    """이닝별 타순을 재구성해 타석 순서대로 [(타자 index, 이닝, 코드)] 반환"""
    if not bat:
        return []
    n_inn = max(len(b['inn']) for b in bat)
    slots = sorted({b['slot'] for b in bat if b['slot']})
    if not slots:
        return []
    seq, nxt = [], 0  # nxt: 다음 이닝 첫 타자의 slots index
    for j in range(n_inn):
        queues = {}
        for i, b in enumerate(bat):
            if j < len(b['inn']):
                for c in b['inn'][j]:
                    queues.setdefault(b['slot'], []).append((i, j, c))
        if not queues:
            continue
        # 시작 타순: 직전 이닝 다음 타자. 그 타순이 이번 이닝에 기록이 없으면 기록이 있는 첫 타순부터
        k = nxt
        if slots[k % len(slots)] not in queues:
            for step in range(len(slots)):
                if slots[(nxt + step) % len(slots)] in queues:
                    k = nxt + step
                    break
        last = k
        while any(queues.values()):
            s = slots[k % len(slots)]
            q = queues.get(s)
            if q:
                seq.append(q.pop(0))
                last = k
            k += 1
            if k - last > len(slots):  # 안전장치
                break
        nxt = (last + 1) % len(slots)
    return seq


BIP = ('1B', '2B', '3B', 'HR', 'GO', 'FO', 'LO', 'E', 'FC', 'SF', 'SH', 'OUT')


def assign_pitchers(seq, pits, bat):
    """타석 순서와 투수별 상대 타자 수(BF)로 투수 배정 → 투수별 타구 성향 집계"""
    agg = [dict(go=0, fo=0, lo=0, ih=0, ofh=0, bf_seq=0) for _ in pits]
    who = []
    k = 0
    for pi, p in enumerate(pits):
        n = p.get('bf', 0)
        who += [pi] * n
    for idx, (bi, j, c) in enumerate(seq):
        pi = who[idx] if idx < len(who) else (len(pits) - 1 if pits else None)
        if pi is None:
            continue
        a = agg[pi]
        a['bf_seq'] += 1
        kind = c.split(':')[0]
        if kind == 'GO':
            a['go'] += 1
        elif kind in ('FO', 'SF'):
            a['fo'] += 1
        elif kind == 'LO':
            a['lo'] += 1
        elif kind in ('1B', '2B', '3B', 'HR'):
            if c.endswith(':IH'):
                a['ih'] += 1
            else:
                a['ofh'] += 1
    # 검증용: 배정된 타석의 삼진·볼넷 수를 투수 기록과 비교
    chk = [dict(k=0, bb=0) for _ in pits]
    for idx, (bi, j, c) in enumerate(seq):
        if idx < len(who):
            if c == 'K':
                chk[who[idx]]['k'] += 1
            elif c == 'BB':
                chk[who[idx]]['bb'] += 1
    return agg, chk


def process(raw):
    games, issues = [], []
    stat = dict(pa=0, bf=0, pit_ok=0, pit_n=0)
    res_by = {g['gid']: g for g in raw['results']}
    for gid, g in raw['games'].items():
        r = res_by[gid]
        t = g.get('t', [])
        if len(t) < 4 or len(t[0]) < 2:
            games.append(dict(id=gid, d=r['d'], t=r['t'], lg=r['lg'], a=r['a'], b=r['b'], sc=r['sc'], nobox=True))
            continue
        bats = [parse_bat(t[0]), parse_bat(t[2])]
        pits = [parse_pit(t[1]), parse_pit(t[3])]
        if not bats[0] and not bats[1]:  # 몰수 경기 등 선수 기록이 없는 경기
            games.append(dict(id=gid, d=r['d'], t=r['t'], lg=r['lg'], a=r['a'], b=r['b'], sc=r['sc'], nobox=True))
            continue
        # 각 팀 타자 기록과 박스 숫자 검증
        for side in (0, 1):
            for b in bats[side]:
                codes = [c for inn in b['inn'] for c in inn]
                ab = sum(1 for c in codes if c.split(':')[0] in ('1B', '2B', '3B', 'HR', 'GO', 'FO', 'LO', 'E', 'FC', 'K', 'OUT'))
                h = sum(1 for c in codes if c.split(':')[0] in ('1B', '2B', '3B', 'HR'))
                if ab != b['box'].get('ab') or h != b['box'].get('h'):
                    issues.append(f"{r['d']} {b['name']} ab {ab}/{b['box'].get('ab')} h {h}/{b['box'].get('h')}")
        # 투수 배정: 0팀 타자 ↔ 1팀 투수
        pagg = [None, None]
        for side in (0, 1):
            seq = pa_sequence(bats[side])
            fp = pits[1 - side]
            agg, chk = assign_pitchers(seq, fp, bats[side])
            stat['pa'] += len(seq)
            stat['bf'] += sum(p.get('bf', 0) for p in fp)
            for p, c in zip(fp, chk):
                stat['pit_n'] += 1
                if c['k'] == p.get('k', 0) and c['bb'] == p.get('bb', 0):
                    stat['pit_ok'] += 1
            pagg[1 - side] = agg
        teams = g.get('teams', [])

        def rheb(i):
            nums = re.findall(r'\d+', teams[i]) if i < len(teams) else []
            return [int(x) for x in nums[-4:]] if len(nums) >= 4 else None

        games.append(dict(
            id=gid, d=r['d'], t=r['t'], lg=r['lg'], a=r['a'], b=r['b'], sc=r['sc'],
            rheb=[rheb(0), rheb(1)], line=g.get('rounds', []),
            bat=[[[b['slot'], b['name'], b['pos'], ['|'.join(x) for x in b['inn']],
                   [b['box'].get(k, 0) for k in ('ab', 'h', 'tb', 'rbi', 'r', 'sb', 'sh', 'sf', 'bb', 'hbp', 'k', 'gdp')]]
                  for b in bats[s]] for s in (0, 1)],
            pit=[[[p['name'], p.get('dec', ''), p.get('ip', ''),
                   [p.get(k, 0) for k in ('bf', 'ab', 'h', 'hr', 'sac', 'bb', 'hbp', 'k', 'wp', 'bk', 'r', 'er')],
                   [a['go'], a['fo'], a['lo'], a['ih'], a['ofh']]]
                  for p, a in zip(pits[s], pagg[s])] for s in (0, 1)],
        ))
    sched = [dict(d=s['d'], t=s['t'], a=s['a'], b=s['b'], lg=s['lg'], v=s['v']) for s in raw['sched']]
    games.sort(key=lambda x: (x['d'], x['t']))
    return dict(year=raw['year'], at=raw['at'], sched=sched, games=games), issues, stat


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    raw = json.load(open(src, encoding='utf-8'))
    out, issues, stat = process(raw)
    json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('games', len(out['games']), 'sched', len(out['sched']))
    print('PA seq vs BF:', stat, f"pitchers matching K&BB: {stat['pit_ok']}/{stat['pit_n']}")
    print('issues', len(issues))
    for x in issues[:30]:
        print(' ', x)
