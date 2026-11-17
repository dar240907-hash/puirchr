/* Моя аптечка: список, добавление, правка, удаление, напоминания в браузере */
(() => {
  'use strict';
  const S = window.Shukai;
  if (!S || !S.requireAuth()) return;
  const D = S.data;
  const el = S.el;
  const $ = (sel, root = document) => root.querySelector(sel);

  const grid = $('[data-kit-grid]');
  const emptyBox = $('[data-kit-empty]');
  const dialog = $('[data-kit-dialog]');
  const form = $('[data-kit-form]');
  const errorBox = $('[data-error]', form);
  const pickBlock = $('[data-pick-block]');
  const pickList = $('[data-pick-list]');
  const selectedBox = $('[data-selected]');
  const timesBox = $('[data-times]');

  let items = [];
  let editingId = null;  // null — добавление
  let selectedMed = null; // { id, title }

  const medUrl = (id) => D.urlMedication.replace('/0/', `/${id}/`);
  const kitItemUrl = (id) => D.apiKitItem.replace('/0/', `/${id}/`);

  // 1 дзень / 2–4 дні / 5+ дзён
  function days(n) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return `${n} дзень`;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return `${n} дні`;
    return `${n} дзён`;
  }

  function icon(name) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', `#i-${name}`);
    svg.append(use);
    return svg;
  }

  function button(label, iconName, className, onClick) {
    const b = el('button', className);
    b.type = 'button';
    b.append(icon(iconName), document.createTextNode(label));
    b.addEventListener('click', onClick);
    return b;
  }

  /* ---------- список ---------- */

  function render() {
    grid.replaceChildren();
    emptyBox.hidden = items.length > 0;

    items.forEach((it) => {
      const info = it.medication_info || {};
      const card = el('article', 'card kit-card');

      const top = el('div', 'kit-card__top');
      const box = el('span', 'icon-box');
      box.append(icon('pill'));
      const head = el('div');
      const h3 = el('h3');
      const link = el('a', '', info.title || 'Прэпарат');
      link.href = medUrl(it.medication);
      h3.append(link);
      head.append(h3, el('p', '', [info.inn_name, info.dosage].filter(Boolean).join(' · ')));
      top.append(box, head);

      const stats = el('div', 'kit-stats');
      [[it.quantity_remaining, 'засталося'], [it.dosage_per_day, 'прыёмаў у дзень'], [it.course_days_left, 'дзён курсу']]
        .forEach(([value, label]) => {
          const s = el('div', 'stat');
          s.append(el('b', '', String(value)), el('span', '', label));
          stats.append(s);
        });

      const badges = el('div', 'badges');
      const perDay = Math.max(1, it.dosage_per_day);
      const supply = Math.floor(it.quantity_remaining / perDay);
      if (it.quantity_remaining <= 0) badges.append(el('span', 'warn-badge warn-badge--red', 'Лекі скончыліся'));
      else if (supply <= 3) badges.append(el('span', 'warn-badge', `Хопіць на ${days(supply)}`));
      if (it.quantity_remaining > 0 && it.course_days_left > supply) {
        badges.append(el('span', 'warn-badge', 'Не хопіць на ўвесь курс'));
      }

      const times = el('div', 'times');
      const timeList = Array.isArray(it.reminder_times) ? it.reminder_times : [];
      if (timeList.length) {
        timeList.forEach((t) => {
          const chip = el('span', 'time-chip');
          chip.append(icon('clock'), document.createTextNode(String(t)));
          times.append(chip);
        });
      } else {
        times.append(el('span', 'form-hint', 'Напамінкі не зададзены'));
      }

      const actions = el('div', 'kit-actions');
      actions.append(
        button('Прыняў', 'check', 'btn btn--ghost', () => takeDose(it)),
        button('Рэдагаваць', 'pencil', 'btn btn--ghost', () => openDialog(it)),
        button('Выдаліць', 'trash', 'btn btn--ghost btn--danger', () => remove(it)),
      );

      card.append(top, stats);
      if (badges.children.length) card.append(badges);
      card.append(times, actions);
      grid.append(card);
    });
  }

  async function load() {
    const res = await S.api(D.apiKit, { auth: 'required' });
    if (res.status === 401) { S.store.set(null); S.requireAuth(); return; }
    if (!res.ok) { S.toast(S.errorText(res.data, 'Не ўдалося загрузіць аптэчку.'), 'error'); return; }
    items = Array.isArray(res.data) ? res.data : [];
    render();
  }

  async function takeDose(it) {
    if (it.quantity_remaining <= 0) { S.toast('Лекі скончыліся', 'error'); return; }
    const res = await S.api(kitItemUrl(it.id), {
      method: 'PATCH',
      body: { quantity_remaining: it.quantity_remaining - 1 },
      auth: 'required',
    });
    if (!res.ok) { S.toast(S.errorText(res.data, 'Не ўдалося абнавіць.'), 'error'); return; }
    Object.assign(it, res.data);
    render();
  }

  async function remove(it) {
    const title = (it.medication_info && it.medication_info.title) || 'прэпарат';
    if (!window.confirm(`Выдаліць «${title}» з аптэчкі?`)) return;
    const res = await S.api(kitItemUrl(it.id), { method: 'DELETE', auth: 'required' });
    if (!res.ok) { S.toast(S.errorText(res.data, 'Не ўдалося выдаліць.'), 'error'); return; }
    items = items.filter((x) => x.id !== it.id);
    render();
    S.toast('Выдалена');
  }

  /* ---------- диалог добавления / правки ---------- */

  function addTimeInput(value) {
    const wrap = el('span', 'time-item');
    const input = el('input', 'input');
    input.type = 'time';
    input.value = value || '08:00';
    input.setAttribute('aria-label', 'Час напамінка');
    const del = el('button', 'btn btn--ghost btn--danger');
    del.type = 'button';
    del.setAttribute('aria-label', 'Прыбраць час');
    del.append(icon('x'));
    del.addEventListener('click', () => wrap.remove());
    wrap.append(input, del);
    timesBox.insertBefore(wrap, timesBox.querySelector('[data-add-time]'));
  }

  function resetTimes(values) {
    timesBox.replaceChildren();
    const add = el('button', 'btn btn--ghost');
    add.type = 'button';
    add.dataset.addTime = '';
    add.append(icon('plus'), document.createTextNode('Дадаць час'));
    add.addEventListener('click', () => addTimeInput());
    timesBox.append(add);
    (values && values.length ? values : []).forEach(addTimeInput);
  }

  function setSelected(med) {
    selectedMed = med;
    selectedBox.hidden = !med;
    $('[data-selected-title]').textContent = med ? med.title : '';
  }

  function setError(text) {
    errorBox.textContent = text || '';
    errorBox.hidden = !text;
  }

  function openDialog(item, preset) {
    editingId = item ? item.id : null;
    setError('');
    pickList.replaceChildren();
    $('#kit-search').value = '';
    $('[data-kit-title]').textContent = item ? 'Змяніць запіс' : 'Дадаць прэпарат';
    pickBlock.hidden = Boolean(item);

    if (item) {
      setSelected({ id: item.medication, title: (item.medication_info && item.medication_info.title) || 'Прэпарат' });
      form.quantity_remaining.value = item.quantity_remaining;
      form.dosage_per_day.value = item.dosage_per_day;
      form.course_days_left.value = item.course_days_left;
      resetTimes(item.reminder_times);
    } else {
      setSelected(preset || null);
      form.quantity_remaining.value = 20;
      form.dosage_per_day.value = 1;
      form.course_days_left.value = 7;
      resetTimes(['08:00']);
    }
    dialog.showModal();
  }

  function closeDialog() { dialog.close(); }

  async function pickSearch() {
    const q = $('#kit-search').value.trim();
    if (!q) return;
    pickList.replaceChildren(el('p', 'form-hint', 'Шукаем…'));
    const res = await S.api(`${D.apiSearch}?q=${encodeURIComponent(q)}`, { auth: 'none' });
    pickList.replaceChildren();
    if (!res.ok || !res.data || !res.data.product) {
      pickList.append(el('p', 'form-hint', 'Прэпарат не знойдзены. Паспрабуйце іншую назву.'));
      return;
    }
    const found = [res.data.product, ...(res.data.analogs || [])];
    found.forEach((p) => {
      const b = el('button', 'pick');
      b.type = 'button';
      const left = el('b', '', p.title);
      const right = el('span', '', p.country || '');
      b.append(left, right);
      b.addEventListener('click', () => {
        setSelected({ id: p.id, title: p.title });
        pickList.replaceChildren();
      });
      pickList.append(b);
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    setError('');

    if (!selectedMed) { setError('Абярыце прэпарат.'); return; }
    const quantity = Number(form.quantity_remaining.value);
    const perDay = Number(form.dosage_per_day.value);
    const courseDays = Number(form.course_days_left.value);
    if (![quantity, perDay, courseDays].every(Number.isInteger) || quantity < 0 || perDay < 1 || courseDays < 0) {
      setError('Праверце лічбы: цэлыя, не менш за 0 (прыёмаў у дзень — не менш за 1).');
      return;
    }
    const times = Array.from(new Set(
      Array.from(timesBox.querySelectorAll('input[type="time"]')).map((i) => i.value).filter(Boolean),
    )).sort();

    const payload = {
      quantity_remaining: quantity,
      dosage_per_day: perDay,
      course_days_left: courseDays,
      reminder_times: times,
    };

    const submit = $('button[type="submit"]', form);
    submit.disabled = true;
    let res;
    if (editingId) {
      res = await S.api(kitItemUrl(editingId), { method: 'PATCH', body: payload, auth: 'required' });
    } else {
      res = await S.api(D.apiKit, { method: 'POST', body: { ...payload, medication: selectedMed.id }, auth: 'required' });
    }
    submit.disabled = false;

    if (!res.ok) { setError(S.errorText(res.data, 'Не ўдалося захаваць.')); return; }
    closeDialog();
    S.toast('Захавана');
    await load();
  });

  $('[data-kit-add]').addEventListener('click', () => openDialog(null));
  document.querySelectorAll('[data-kit-close]').forEach((b) => b.addEventListener('click', closeDialog));
  $('[data-pick-search]').addEventListener('click', pickSearch);
  $('#kit-search').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); pickSearch(); } });
  dialog.addEventListener('click', (e) => { if (e.target === dialog) closeDialog(); });

  /* ---------- напоминания в браузере ---------- */

  const notifyBtn = $('[data-notify-btn]');
  const notifyHint = $('[data-notify-hint]');
  const fired = new Set();

  function reminderTick() {
    const now = new Date();
    const hhmm = now.toTimeString().slice(0, 5);
    const day = now.toDateString();
    items.forEach((it) => {
      if (!Array.isArray(it.reminder_times) || !it.reminder_times.includes(hhmm)) return;
      const key = `${it.id}|${hhmm}|${day}`;
      if (fired.has(key)) return;
      fired.add(key);
      const title = (it.medication_info && it.medication_info.title) || 'лекі';
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Час прыняць лекі', { body: title });
      }
      S.toast(`Час прыняць: ${title}`);
    });
  }

  function syncNotifyUi() {
    const supported = 'Notification' in window;
    const granted = supported && Notification.permission === 'granted';
    notifyBtn.hidden = !supported || granted;
    notifyHint.hidden = !granted;
  }

  notifyBtn.addEventListener('click', async () => {
    const result = await Notification.requestPermission();
    syncNotifyUi();
    if (result !== 'granted') S.toast('Дазвол на апавяшчэнні не атрыманы', 'error');
  });

  syncNotifyUi();
  setInterval(reminderTick, 20000);

  /* ---------- старт ---------- */

  (async () => {
    await load();
    // Переход со страницы препарата: ?add=ID&title=...
    const params = new URLSearchParams(location.search);
    const addId = Number(params.get('add'));
    if (Number.isInteger(addId) && addId > 0) {
      const title = params.get('title') || 'Прэпарат';
      history.replaceState(null, '', location.pathname);
      openDialog(null, { id: addId, title });
    }
  })();
})();
