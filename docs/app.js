const $ = s => document.querySelector(s);
const state = { all: [], fb: [], source: 'all', q: '', onlyNew: false, updated: null };
const LAST_KEY = 'lastVisit';
const lastVisit = Number(localStorage.getItem(LAST_KEY) || 0);

const ago = iso => {
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 1) return 'только что';
  if (m < 60) return `${m} мин назад`;
  if (m < 1440) return `${Math.round(m / 60)} ч назад`;
  return `${Math.round(m / 1440)} дн назад`;
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function render() {
  const q = state.q.toLowerCase();
  let items = state.all.filter(i =>
    (state.source === 'all' || state.source === i.source) &&
    (!q || (i.title + ' ' + i.params.join(' ') + ' ' + i.location).toLowerCase().includes(q)) &&
    (!state.onlyNew || new Date(i.first_seen) > lastVisit));
  const html = [];
  if (state.source === 'facebook' || state.source === 'all') {
    html.push(...state.fb.map(f => `<a class="card" href="${esc(f.url)}" target="_blank" rel="noopener">
      <div class="noimg"></div><div class="body"><div class="title">${esc(f.name)}</div>
      <div class="meta">Facebook закрыт для ботов — открыть поиск вручную ↗</div>
      <div class="tags"><span class="tag">facebook</span></div></div></a>`));
  }
  if (state.source === 'facebook') items = [];
  html.push(...items.slice(0, 300).map(i => {
    const isNew = new Date(i.first_seen) > lastVisit;
    return `<a class="card" href="${esc(i.url)}" target="_blank" rel="noopener">
      ${i.image ? `<img loading="lazy" src="${esc(i.image)}" alt="">` : '<div class="noimg"></div>'}
      <div class="body">
        <div class="row"><div class="title">${esc(i.title)}</div><div class="price">${esc(i.price)}</div></div>
        <div class="meta">${esc(i.params.join(' · '))}</div>
        <div class="tags"><span class="tag">${esc(i.source)}</span>${isNew ? '<span class="tag new">новое</span>' : ''}
          <span class="tag">${ago(i.first_seen)}</span></div>
      </div></a>`;
  }));
  $('#list').innerHTML = html.join('') || '<div class="empty">Ничего не найдено</div>';
}

async function load() {
  try {
    const d = await (await fetch('listings.json?t=' + Date.now())).json();
    state.all = d.listings; state.fb = d.facebook_searches || []; state.updated = d.updated;
    $('#status').textContent = `обновлено ${ago(d.updated)} · ${d.listings.length} шт.`;
  } catch { $('#status').textContent = 'нет данных (офлайн?)'; }
  render();
}

$('#q').addEventListener('input', e => { state.q = e.target.value; render(); });
$('#onlyNew').addEventListener('change', e => { state.onlyNew = e.target.checked; render(); });
$('#sources').addEventListener('click', e => {
  if (!e.target.dataset.s) return;
  state.source = e.target.dataset.s;
  document.querySelectorAll('#sources button').forEach(b => b.classList.toggle('on', b === e.target));
  render();
});
document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && load());
window.addEventListener('pagehide', () => localStorage.setItem(LAST_KEY, Date.now()));
setInterval(load, 5 * 60 * 1000);
load();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js');
