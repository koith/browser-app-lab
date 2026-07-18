// /api/daangn-regions.js — 서울/경기 시군구 코드 자동 제공
// GET /api/daangn-regions  →  { list:[{code,name,province}], total }
// 당근 /kr/regions/ 페이지(전국 시군구 코드 244개)를 파싱해 서울·경기만 분류

export const config = { maxDuration: 30 };

const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const SEOUL = ['종로구','중구','용산구','성동구','광진구','동대문구','중랑구','성북구','강북구','도봉구',
  '노원구','은평구','서대문구','마포구','양천구','강서구','구로구','금천구','영등포구','동작구',
  '관악구','서초구','강남구','송파구','강동구'];

const GYEONGGI = ['수원시','성남시','고양시','용인시','부천시','안산시','안양시','남양주시','화성시','평택시',
  '의정부시','시흥시','파주시','광명시','김포시','군포시','광주시','이천시','양주시','오산시',
  '구리시','안성시','포천시','의왕시','하남시','여주시','동두천시','과천시','가평군','양평군','연천군'];

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  let html;
  try {
    const r = await fetch('https://www.daangn.com/kr/regions/', {
      headers: { 'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9' },
      redirect: 'follow',
    });
    if (!r.ok) return res.status(502).json({ error: `daangn HTTP ${r.status}` });
    html = await r.text();
  } catch (e) {
    return res.status(502).json({ error: String(e.message || e).slice(0, 200) });
  }

  // 페이지 내 모든 지역 코드 수집
  const codes = new Set();
  for (const m of html.matchAll(/[?&](?:amp;)?in=([^"&#\s]+)/g)) {
    let c;
    try { c = decodeURIComponent(m[1]); } catch { continue; }
    if (/^[가-힣0-9]+(?:-[가-힣0-9]+)*-\d+$/.test(c)) codes.add(c);
  }

  // 서울/경기 분류 (코드명은 "서초구-362" 또는 "수원시-권선구-1270" 형태)
  const items = [];
  for (const code of codes) {
    const name = code.replace(/-\d+$/, '');       // 예: 수원시-권선구
    const head = name.split('-')[0];              // 예: 수원시
    if (SEOUL.includes(name)) {
      items.push({ code, name, province: '서울특별시' });
    } else if (GYEONGGI.includes(head)) {
      items.push({ code, name: name.replace(/-/g, ' '), province: '경기도', head });
    }
  }

  // 시 전체 코드가 있으면 그 시의 하위 구 코드는 제외 (중복 조회 방지)
  const wholeCities = new Set(items.filter(i => i.head && i.name === i.head).map(i => i.head));
  const filtered = items.filter(i => !(i.head && i.name !== i.head && wholeCities.has(i.head)));

  filtered.sort((a, b) => (a.province === b.province ? a.name.localeCompare(b.name, 'ko') : a.province === '서울특별시' ? -1 : 1));
  const list = filtered.map(({ code, name, province }) => ({ code, name, province }));

  res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=604800');
  return res.status(200).json({
    total: list.length,
    seoul: list.filter(r => r.province === '서울특별시').length,
    gyeonggi: list.filter(r => r.province === '경기도').length,
    list,
  });
}
