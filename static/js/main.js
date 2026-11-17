/* Шукай Сваё — клиентская логика: фильтры каталога, текстовый и фото-поиск */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const API_SEARCH = document.body.dataset.apiSearch;
  const API_PHOTO = document.body.dataset.apiPhoto;

  /* ---------- helpers ---------- */

  // 1 прэпарат / 2–4 прэпараты / 5+ прэпаратаў
  function plural(n) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return 'прэпарат';
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return 'прэпараты';
    return 'прэпаратаў';
  }

  // Безопасное создание DOM (никакого innerHTML с данными от сервера/ИИ)
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  const money = (v) => `${Number(v).toFixed(2)} BYN`;
  const medicationUrl = (id) => document.body.dataset.urlMedication.replace('/0/', `/${id}/`);

  /* ---------- блок результата поиска ---------- */

  const resultBox = $('[data-result]');

  function showResult(kind, build) {
    if (!resultBox) return;
    resultBox.replaceChildren();
    resultBox.className = 'result' + (kind ? ` result--${kind}` : '');
    resultBox.hidden = false;
    build(resultBox);
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showLoading(text) {
    showResult('loading', (box) => box.append(el('p', '', text)));
  }

  function showError(text) {
    showResult('error', (box) => {
      box.append(el('h3', '', 'Не атрымалася выканаць пошук'));
      box.append(el('p', '', text));
    });
  }

  function renderSearch(data) {
    if (data.status === 'not_found') {
      showResult('', (box) => {
        box.append(el('h3', '', 'Прэпарат не знойдзены'));
        box.append(el('p', '', data.message || 'Паспрабуйце іншую назву або МНН.'));
        if (data.recognized_text) {
          box.append(el('p', '', `Распазнана на фота: ${data.recognized_text}`));
        }
      });
      return;
    }

    const product = data.product || {};
    const analogs = data.analogs || [];

    showResult('', (box) => {
      box.append(el('h3', '', `Знойдзена: ${product.title}`));
      const meta = [];
      if (product.country) meta.push(product.country);
      if (product.inn_name) meta.push(`МНН: ${product.inn_name}`);
      if (product.price != null) meta.push(money(product.price));
      if (meta.length) box.append(el('p', '', meta.join(' · ')));
      if (product.id) {
        const open = el('a', 'link-arrow', 'Адкрыць старонку прэпарата');
        open.href = medicationUrl(product.id);
        open.style.marginTop = '10px';
        box.append(open);
      }
      if (data.recognized_text) {
        box.append(el('p', '', `Распазнана на фота: ${data.recognized_text}`));
      }

      box.append(el('h3', '', 'Аналагі'));
      box.lastChild.style.marginTop = '20px';

      if (!analogs.length) {
        box.append(el('p', '', 'Аналагі пакуль не знойдзены.'));
        return;
      }

      const list = el('div', 'result__list');
      analogs.forEach((a) => {
        const item = el('a', 'result__item');
        if (a.id) item.href = medicationUrl(a.id);
        const left = el('div');
        left.append(el('b', '', a.title));
        const sub = [a.country, a.status].filter(Boolean).join(' · ');
        if (sub) {
          left.append(document.createElement('br'));
          left.append(el('span', '', sub));
        }
        item.append(left, el('b', '', money(a.price)));
        list.append(item);
      });
      box.append(list);
    });
  }

  async function textSearch(query) {
    const q = query.trim();
    if (!q || !API_SEARCH) return;
    showLoading('Шукаем…');
    try {
      const res = await fetch(`${API_SEARCH}?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (!res.ok && data.status !== 'not_found') {
        throw new Error(data.message || `Памылка ${res.status}`);
      }
      renderSearch(data);
    } catch (err) {
      showError(err.message || 'Праверце злучэнне і паспрабуйце яшчэ раз.');
    }
  }

  async function photoSearch(file) {
    if (!file || !API_PHOTO) return;
    showLoading('Штучны інтэлект распазнае ўпакоўку…');
    const body = new FormData();
    body.append('image', file);
    try {
      const res = await fetch(API_PHOTO, { method: 'POST', body });
      const data = await res.json();
      if (!res.ok && data.status !== 'not_found') {
        throw new Error(data.message || `Памылка ${res.status}`);
      }
      renderSearch(data);
    } catch (err) {
      showError(err.message || 'Не ўдалося апрацаваць фота.');
    }
  }

  /* ---------- фото: кнопка -> input[type=file] ---------- */

  $$('[data-photo-trigger]').forEach((btn) => {
    const input = btn.parentElement.querySelector('[data-photo-input]');
    if (!input) return;
    btn.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (file) photoSearch(file);
      input.value = '';
    });
  });

  /* ---------- страница каталога ---------- */

  const grid = $('[data-med-grid]');
  if (grid) {
    const cards = $$('.med-card', grid);
    const empty = $('[data-empty]', grid);
    const counter = $('[data-count]');
    const state = { category: 'all', status: 'all', country: 'all', sort: 'by' };

    // Категории работают, только если у карточек есть data-category
    // (в модели Medication пока нет поля category).
    const hasCategories = cards.some((c) => c.dataset.category);

    function apply() {
      let visible = 0;
      cards.forEach((c) => {
        const ok =
          (state.status === 'all' || c.dataset.status === state.status) &&
          (state.country === 'all' || c.dataset.by === '1') &&
          (!hasCategories || state.category === 'all' || c.dataset.category === state.category);
        c.hidden = !ok;
        if (ok) visible += 1;
      });

      const byTitle = (a, b) => a.dataset.title.localeCompare(b.dataset.title, 'be');
      const sorted = cards.slice().sort((a, b) =>
        state.sort === 'price'
          ? Number(a.dataset.price) - Number(b.dataset.price) || byTitle(a, b)
          : Number(b.dataset.by) - Number(a.dataset.by) || byTitle(a, b)
      );
      sorted.forEach((c) => grid.appendChild(c));
      if (empty) {
        grid.appendChild(empty);
        empty.hidden = visible !== 0;
      }
      if (counter) counter.textContent = `Знойдзена ${visible} ${plural(visible)}`;
    }

    $$('[data-filter]').forEach((group) => {
      const key = group.dataset.filter;
      group.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip');
        if (!chip || !group.contains(chip)) return;
        $$('.chip', group).forEach((c) => c.classList.toggle('is-active', c === chip));
        state[key] = chip.dataset.value;
        apply();
      });
    });

    apply();

    // Поиск по названию / МНН
    const form = $('[data-search-form]');
    const input = $('[data-search-input]');
    const submitBtn = $('[data-search-submit]');
    if (form && input) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        textSearch(input.value);
      });
      if (submitBtn) submitBtn.addEventListener('click', () => form.requestSubmit());

      const initial = new URLSearchParams(window.location.search).get('q');
      if (initial) {
        input.value = initial;
        textSearch(initial);
      }
    }
  }
})();
