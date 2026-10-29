/* Private original gallery connector: credentials stay in sessionStorage only.
 * Same owner TeraBox gateway used by both galleries. No server secrets in HTML.
 * Only a user submit can authenticate; publicly accessible Pages cannot fetch
 * owner-only originals without an explicit bearer token.
 */
(() => {
  'use strict';
  const script = document.currentScript;
  const model = script && script.dataset.model;
  if (model !== 'yui' && model !== 'mimmi') return;
  const API = 'https://mimmi-private-gallery-free.onrender.com';
  const KEY = model + '-owner-session';
  const PATH = model === 'yui' ? '/api/yui/catalog' : '/api/catalog';
  const MODEL_NAME = model === 'yui' ? '심유이' : '밈미';
  const $ = id => document.getElementById(id);
  function session() {
    try {
      const s = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      return s && s.api === API && typeof s.token === 'string' && s.token.length >= 12 ? s : null;
    } catch { return null; }
  }
  async function request(token) {
    // A private account connection is never probed using an untrusted URL.
    const controller = new AbortController();
    const stop = setTimeout(() => controller.abort(), 26000);
    try {
      const response = await fetch(API + PATH, {
        method: 'GET', credentials: 'omit', cache: 'no-store',
        headers: {'Authorization': 'Bearer ' + token},
        referrerPolicy: 'no-referrer', signal: controller.signal
      });
      if (response.status === 401 || response.status === 403)
        throw new Error('접근 토큰이 맞지 않습니다.');
      if (response.status === 502 || response.status === 503 || response.status === 504)
        throw new Error('테라박스 보관본 검증 또는 연결이 아직 완료되지 않았습니다.');
      if (!response.ok) throw new Error('보관소 응답 HTTP ' + response.status);
      const data = await response.json();
      if (data.model !== model || data.schema_version !== 1 || !Array.isArray(data.albums))
        throw new Error('잘못된 모델의 보관소 자료가 반환됐습니다.');
      let count = 0;
      const identifiers = new Set();
      for (const album of data.albums) {
        if (typeof album.id !== 'string' || identifiers.has(album.id)
          || !/^[a-z0-9][a-z0-9-]{1,100}$/.test(album.id)
          || !Array.isArray(album.images)) throw new Error('보관소 목록 검증에 실패했습니다.');
        identifiers.add(album.id);
        const slots = new Set();
        for (const photo of album.images) {
          if (!Number.isSafeInteger(photo.number) || photo.number < 1
            || slots.has(photo.number) || !Number.isSafeInteger(photo.bytes)
            || photo.bytes <= 0 || !/^[a-f0-9]{64}$/.test(photo.sha256))
            throw new Error('보관소의 저장 사진 기록이 올바르지 않습니다.');
          slots.add(photo.number); count++;
        }
      }
      if (!count) throw new Error('현재 이 보관소에 게시된 저장 사진이 없습니다.');
      return {count, albums: data.albums.length};
    } finally { clearTimeout(stop); }
  }
  function initialize() {
    const browse = $('browse');
    const vault = browse && browse.querySelector('.vault-actions');
    if (!vault) return;
    const panel = document.createElement('section');
    panel.id = 'owner-gallery-connector';
    panel.className = 'private-gallery-connector';
    panel.setAttribute('aria-label', MODEL_NAME + ' 개인 보관소 연결');
    panel.innerHTML = '<div class="pg-copy">'
      + '<p class="pg-title">테라박스에 이미 저장한 ' + MODEL_NAME + ' 원본 불러오기</p>'
      + '<p class="pg-caption">공개 저장본만 보인다면 개인 보관소를 연결하세요. 인증 후 이미 저장된 화보·사진이 이 목록에 바로 합쳐집니다. 사진을 다시 업로드할 필요가 없습니다.</p>'
      + '</div><button class="pg-action" type="button" id="pg-toggle" aria-expanded="false">내 보관 원본 연결</button>'
      + '<form class="pg-form" id="pg-form" hidden>'
      + '<input id="pg-token" type="password" autocomplete="off" spellcheck="false" aria-label="개인 갤러리 접근 토큰" placeholder="갤러리 접근 토큰" required>'
      + '<button class="pg-action" id="pg-submit" type="submit">저장된 원본 열기</button>'
      + '<button id="pg-cancel" type="button">취소</button>'
      + '</form>'
      + '<p class="pg-status" id="pg-status" role="status" aria-live="polite"></p>';
    vault.insertAdjacentElement('beforebegin', panel);
    const btn = $('pg-toggle');
    const form = $('pg-form');
    const password = $('pg-token');
    const status = $('pg-status');
    const submit = $('pg-submit');
    const setStatus = (value, good = false) => {
      status.textContent = value;
      status.dataset.good = String(good);
    };
    btn.addEventListener('click', () => {
      const open = form.hidden;
      form.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      if (open) password.focus();
    });
    $('pg-cancel').addEventListener('click', () => {
      form.hidden = true;
      password.value = '';
      btn.setAttribute('aria-expanded', 'false');
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const token = password.value.trim();
      if (token.length < 12 || token.length > 2048) {
        setStatus('앞서 발급된 개인 갤러리 접근 토큰 전체를 입력하세요.');
        return;
      }
      submit.disabled = true;
      setStatus('실제 테라박스 저장 사진 목록을 확인하는 중…');
      try {
        const physical = await request(token);
        sessionStorage.setItem(KEY, JSON.stringify({api: API, token}));
        password.value = '';
        setStatus('연결 성공: 저장된 ' + physical.count.toLocaleString('ko-KR')
          + '장 / ' + physical.albums + '개 화보. 목록에 합치는 중…', true);
        location.reload();
      } catch (error) {
        setStatus('연결 실패: ' + (error.name === 'AbortError'
          ? '서버 응답 시간이 초과됐습니다.' : error.message));
      } finally { submit.disabled = false; }
    });
    const saved = session();
    if (!saved) {
      setStatus('이 브라우저는 아직 비공개 보관소에 연결되지 않았습니다. 공개 저장본만 표시됩니다.');
      return;
    }
    btn.textContent = '연결 해제';
    btn.classList.remove('pg-action');
    btn.addEventListener('click', () => {}, {once:true}); // Replaced below without changing initial focus.
    btn.onclick = e => { // Button can show the token field for reconnect on click.
      if (form.hidden) {
        e.stopImmediatePropagation();
        sessionStorage.removeItem(KEY);
        location.reload();
      }
    };
    // Cached membership is not proof of real stored photos; confirm live API.
    setStatus('개인 원본 저장소에 연결 중…');
    request(saved.token).then(physical => {
      setStatus('연결됨: 비공개 보관본 '
        + physical.count.toLocaleString('ko-KR') + '장 / '
        + physical.albums + '개 화보가 기존 목록에 합쳐집니다.', true);
    }).catch(error => {
      setStatus('보관소를 갱신할 수 없습니다: ' + error.message);
    });
  }
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();