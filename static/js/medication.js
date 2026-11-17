/* Страница препарата: калькулятор, карта аптек, цены и отзывы от ИИ */
(() => {
  'use strict';
  const S = window.Shukai;
  const root = document.querySelector('[data-med]');
  if (!S || !root) return;
  const D = S.data;
  const el = S.el;
  const $ = (sel, scope = root) => scope.querySelector(sel);

  const medId = Number(root.dataset.medId);
  const basePrice = Number(root.dataset.price) || 0;
  const pack = Number(root.dataset.pack) > 0 ? Number(root.dataset.pack) : 20; // как в бэкенде
  const money = (v) => `${Number(v).toFixed(2)} BYN`;

  // Ссылки от ИИ пропускаем только если это http(s)
  function safeUrl(value) {
    try {
      const u = new URL(String(value));
      return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : null;
    } catch { return null; }
  }

  function icon(name, className) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', className ? `icon ${className}` : 'icon');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `#i-${name}`);
    svg.append(use);
    return svg;
  }

  /* ---------- калькулятор ---------- */

  const calcForm = $('[data-calc-form]');
  const calcResult = $('[data-calc-result]');
  const calcError = $('[data-error]', calcForm);

  function row(label, value, className) {
    const r = el('div', `calc__row${className ? ` ${className}` : ''}`);
    r.append(el('span', '', label), el('b', '', value));
    return r;
  }

  async function calculate() {
    calcError.hidden = true;
    const days = Number(calcForm.days.value);
    const times = Number(calcForm.times.value);
    if (!Number.isInteger(days) || !Number.isInteger(times) || days < 1 || times < 1 || days > 365 || times > 24) {
      calcError.textContent = 'Увядзіце цэлыя лічбы: дзён ад 1 да 365, прыёмаў у дзень ад 1 да 24.';
      calcError.hidden = false;
      return;
    }

    const res = await S.api(D.apiCalc, {
      method: 'POST',
      body: { medication_id: medId, days, times_per_day: times },
      auth: 'optional',
    });
    if (!res.ok) {
      calcError.textContent = S.errorText(res.data, 'Не ўдалося выканаць разлік.');
      calcError.hidden = false;
      return;
    }

    const d = res.data;
    const packs = Math.ceil(d.pills_needed / pack);
    const discount = Number(d.discount_percent) || 0;
    const wholePacks = packs * basePrice * (1 - discount / 100);

    calcResult.replaceChildren(
      row('Патрэбна таблетак/доз', String(d.pills_needed)),
      row('Кошт без скідкі', money(d.base_cost)),
    );
    if (discount > 0) calcResult.append(row('Скідка', `${discount}%`));
    calcResult.append(row('Да аплаты', money(d.final_cost), 'calc__row--total'));
    calcResult.append(el('p', 'calc__note',
      `Пры куплі цэлых упакоўак (${packs} × ${pack} шт.) выйдзе ${money(wholePacks)}.`));
    if (!S.isLoggedIn()) {
      const note = el('p', 'calc__note');
      const a = el('a', '', 'Увайдзіце');
      a.href = D.urlLogin;
      a.style.color = 'var(--blue)';
      note.append(a, document.createTextNode(', каб улічыць вашу скідку.'));
      calcResult.append(note);
    }
  }

  calcForm.addEventListener('submit', (e) => { e.preventDefault(); calculate(); });
  calculate();

  /* ---------- карта аптек ---------- */

  const mapBlock = $('[data-map-block]');

  async function loadMap() {
    const res = await S.api(`${D.apiMap}?medication_id=${medId}`, { auth: 'none' });
    mapBlock.replaceChildren();

    const pharmacies = res.ok && res.data && Array.isArray(res.data.pharmacies) ? res.data.pharmacies : [];
    if (!pharmacies.length) {
      mapBlock.append(el('p', 'empty-line', 'Пакуль няма даных аб цэнах у аптэках для гэтага прэпарата.'));
      return;
    }

    const wrap = el('div', 'map-wrap');
    const mapEl = el('div');
    mapEl.id = 'pharmacy-map';
    const list = el('div', 'pharm-list');
    wrap.append(mapEl, list);
    mapBlock.append(wrap);

    const canMap = typeof window.L !== 'undefined';
    let map = null;
    const markers = [];

    if (canMap) {
      map = L.map(mapEl, { scrollWheelZoom: false });
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; участники <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
    } else {
      mapEl.hidden = true;
      wrap.style.gridTemplateColumns = '1fr';
    }

    pharmacies.forEach((p, i) => {
      // карточка в списке
      const item = el('button', 'pharm');
      item.type = 'button';
      const title = el('b', '', p.pharmacy_name);
      if (i === 0 && pharmacies.length > 1) title.append(el('span', 'pharm__best', 'Найтаней'));
      item.append(title, el('span', '', p.address), el('span', 'price', money(p.price)));
      if (p.updated_at) item.append(el('span', '', `Абноўлена: ${p.updated_at}`));
      list.append(item);

      if (!map || !Number.isFinite(p.latitude) || !Number.isFinite(p.longitude)) return;

      // маркер на карте (содержимое попапа строим из DOM, без HTML-строк)
      const popup = el('div');
      popup.append(el('b', '', p.pharmacy_name), el('span', '', p.address), el('b', '', money(p.price)));
      const marker = L.marker([p.latitude, p.longitude]).addTo(map).bindPopup(popup);
      markers.push(marker);
      item.addEventListener('click', () => {
        list.querySelectorAll('.pharm').forEach((n) => n.classList.toggle('is-active', n === item));
        map.flyTo([p.latitude, p.longitude], 16, { duration: 0.6 });
        marker.openPopup();
      });
    });

    if (map && markers.length) {
      map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2), { maxZoom: 15 });
      mapEl.addEventListener('click', () => map.scrollWheelZoom.enable(), { once: true });
    } else if (map) {
      map.setView([53.9, 27.5667], 11); // Минск
    }
  }

  /* ---------- цены и отзывы от ИИ ---------- */

  const aiBlock = $('[data-ai-block]');

  function stars(rating) {
    const value = Math.max(0, Math.min(5, Math.round(Number(rating) || 0)));
    const wrap = el('span', 'stars');
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', `Ацэнка ${value} з 5`);
    for (let i = 1; i <= 5; i += 1) wrap.append(icon('star', i > value ? 'off' : ''));
    return wrap;
  }

  async function loadAi() {
    const url = D.apiMedication.replace('/0/', `/${medId}/`);
    const res = await S.api(url, { auth: 'none' });
    aiBlock.replaceChildren();

    if (!res.ok || !res.data) {
      aiBlock.append(el('p', 'empty-line', 'Не ўдалося атрымаць даныя. Паспрабуйце абнавіць старонку пазней.'));
      return;
    }

    const prices = Array.isArray(res.data.ai_prices) ? res.data.ai_prices : [];
    const reviews = Array.isArray(res.data.ai_reviews) ? res.data.ai_reviews : [];

    if (!prices.length && !reviews.length) {
      aiBlock.append(el('p', 'empty-line', 'Штучны інтэлект не знайшоў даных для гэтага прэпарата.'));
      return;
    }

    if (prices.length) {
      const rows = el('div', 'price-rows');
      prices.forEach((p) => {
        const r = el('div', 'price-row');
        const name = el('span', '', String(p.pharmacy || 'Аптэка'));
        const right = el('span');
        const priceNum = Number(p.price);
        right.append(el('b', '', Number.isFinite(priceNum) ? money(priceNum) : '—'));
        const href = safeUrl(p.link);
        if (href) {
          const a = el('a', '', ' Адкрыць');
          a.href = href;
          a.target = '_blank';
          a.rel = 'noopener noreferrer nofollow';
          a.style.marginLeft = '12px';
          right.append(a);
        }
        r.append(name, right);
        rows.append(r);
      });
      aiBlock.append(rows);
    }

    if (reviews.length) {
      const wrap = el('div', 'reviews');
      reviews.forEach((rv) => {
        const card = el('article', 'review');
        const head = el('div');
        head.append(el('b', '', String(rv.author || 'Анонім')), stars(rv.rating));
        card.append(head, el('p', '', String(rv.text || '')));
        wrap.append(card);
      });
      aiBlock.append(wrap);
    }
  }

  loadMap();
  loadAi();
})();
