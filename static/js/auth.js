/* Шукай Сваё — общий слой: JWT-токены, API-клиент, шапка, уведомления.
   Подключается на всех страницах перед остальными скриптами. */
(() => {
  'use strict';

  const D = document.body.dataset;
  const KEY = 'shukai.auth';
  let memory = null; // запасной вариант, если localStorage заблокирован

  const store = {
    get() {
      try { return JSON.parse(localStorage.getItem(KEY)) || memory; } catch { return memory; }
    },
    set(value) {
      memory = value;
      try {
        if (value) localStorage.setItem(KEY, JSON.stringify(value));
        else localStorage.removeItem(KEY);
      } catch { /* хранилище недоступно */ }
    },
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function toast(message, kind) {
    let box = document.querySelector('.toasts');
    if (!box) {
      box = el('div', 'toasts');
      box.setAttribute('aria-live', 'polite');
      document.body.append(box);
    }
    const t = el('div', 'toast' + (kind === 'error' ? ' toast--error' : ''), message);
    box.append(t);
    setTimeout(() => t.remove(), 4500);
  }

  // Достаёт читаемый текст ошибки из ответа DRF
  function errorText(data, fallback) {
    if (!data) return fallback;
    if (typeof data === 'string') return data;
    if (data.error) return String(data.error);
    if (data.detail) return String(data.detail);
    const parts = Object.values(data).map((v) => (Array.isArray(v) ? v.join(' ') : String(v)));
    return parts.join(' ') || fallback;
  }

  async function refresh() {
    const auth = store.get();
    if (!auth || !auth.refresh) return false;
    try {
      const res = await fetch(D.apiRefresh, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: auth.refresh }),
      });
      if (!res.ok) { store.set(null); return false; }
      const data = await res.json();
      store.set({ ...auth, access: data.access, refresh: data.refresh || auth.refresh });
      return true;
    } catch {
      return false;
    }
  }

  /* api(url, { method, body, auth })
       auth: 'required' — отправить токен; 'optional' (по умолчанию) — отправить, если есть;
             'none' — токен не отправлять.
     Возвращает { ok, status, data }. При 401 сам обновляет токен и повторяет запрос. */
  async function api(url, { method = 'GET', body, auth = 'optional' } = {}) {
    const send = () => {
      const headers = {};
      const tokens = store.get();
      if (auth !== 'none' && tokens && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
      let payload;
      if (body instanceof FormData) {
        payload = body;
      } else if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
      }
      return fetch(url, { method, headers, body: payload });
    };

    let res;
    try {
      res = await send();
    } catch {
      return { ok: false, status: 0, data: { error: 'Няма злучэння з серверам.' } };
    }

    // Просроченный токен: DRF отвечает 401 даже на открытых эндпоинтах
    if (res.status === 401 && auth !== 'none' && store.get()) {
      const refreshed = await refresh();
      if (refreshed || auth === 'optional') {
        try { res = await send(); } catch { /* оставим исходный ответ */ }
      }
    }

    let data = null;
    if (res.status !== 204) {
      try { data = await res.json(); } catch { data = null; }
    }
    return { ok: res.ok, status: res.status, data };
  }

  const isLoggedIn = () => Boolean(store.get() && store.get().access);

  function requireAuth() {
    if (isLoggedIn()) return true;
    const next = encodeURIComponent(location.pathname + location.search);
    location.replace(`${D.urlLogin}?next=${next}`);
    return false;
  }

  function login(tokens, username) {
    store.set({ access: tokens.access, refresh: tokens.refresh, username });
  }

  function logout() {
    store.set(null);
    location.href = D.urlHome;
  }

  // Принимаем только внутренние пути вида /abc, чтобы не было редиректа на чужой сайт
  function safeNext(value) {
    return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\')
      ? value
      : null;
  }

  function paintHeader() {
    const logged = isLoggedIn();
    document.querySelectorAll('[data-auth-only]').forEach((n) => { n.hidden = !logged; });
    const slot = document.querySelector('[data-auth-slot]');
    if (!slot || !logged) return;
    slot.href = D.urlProfile;
    const label = slot.querySelector('[data-auth-label]');
    const icon = slot.querySelector('use');
    if (label) label.textContent = 'Кабінет';
    if (icon) icon.setAttribute('href', '#i-user');
  }

  window.Shukai = {
    data: D, store, api, el, toast, errorText,
    isLoggedIn, requireAuth, login, logout, safeNext, paintHeader,
  };

  paintHeader();
})();
