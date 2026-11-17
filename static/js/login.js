/* Страница входа и регистрации */
(() => {
  'use strict';
  const S = window.Shukai;
  if (!S) return;
  const D = S.data;

  const params = new URLSearchParams(location.search);
  const nextParam = params.get('next');
  // next не должен вести обратно на страницу входа — иначе бесконечный редирект
  let next = S.safeNext(nextParam) || D.urlCatalog;
  if (next.startsWith(D.urlLogin)) next = D.urlCatalog;

  if (S.isLoggedIn()) {
    location.replace(next);
    return;
  }

  const tabs = Array.from(document.querySelectorAll('[data-tab]'));
  const panels = Array.from(document.querySelectorAll('[data-panel]'));

  function showTab(name) {
    tabs.forEach((t) => {
      const on = t.dataset.tab === name;
      t.classList.toggle('is-active', on);
      t.setAttribute('aria-selected', String(on));
    });
    panels.forEach((p) => { p.hidden = p.dataset.panel !== name; });
  }
  tabs.forEach((t) => t.addEventListener('click', () => showTab(t.dataset.tab)));

  function setError(form, text) {
    const box = form.querySelector('[data-error]');
    box.textContent = text || '';
    box.hidden = !text;
  }

  async function doLogin(username, password) {
    const res = await S.api(D.apiToken, { method: 'POST', body: { username, password }, auth: 'none' });
    if (!res.ok) {
      return {
        ok: false,
        text: res.status === 401
          ? 'Няправільнае імя карыстальніка або пароль.'
          : S.errorText(res.data, 'Не ўдалося ўвайсці. Паспрабуйце яшчэ раз.'),
      };
    }
    S.login(res.data, username);
    return { ok: true };
  }

  const [loginForm, registerForm] = ['login', 'register'].map((n) => document.querySelector(`[data-panel="${n}"]`));

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    setError(loginForm, '');
    const username = loginForm.username.value.trim();
    const password = loginForm.password.value;
    if (!username || !password) { setError(loginForm, 'Запоўніце імя карыстальніка і пароль.'); return; }

    const btn = loginForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    const result = await doLogin(username, password);
    btn.disabled = false;
    if (result.ok) location.href = next;
    else setError(loginForm, result.text);
  });

  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    setError(registerForm, '');
    const username = registerForm.username.value.trim();
    const email = registerForm.email.value.trim();
    const password = registerForm.password.value;

    if (username.length < 3) { setError(registerForm, 'Імя карыстальніка павінна змяшчаць не менш за 3 сімвалы.'); return; }
    if (password !== registerForm.password2.value) { setError(registerForm, 'Паролі не супадаюць.'); return; }

    const btn = registerForm.querySelector('button[type="submit"]');
    btn.disabled = true;
    const res = await S.api(D.apiRegister, { method: 'POST', body: { username, email, password }, auth: 'none' });
    if (!res.ok) {
      btn.disabled = false;
      setError(registerForm, S.errorText(res.data, 'Не ўдалося стварыць акаўнт.'));
      return;
    }
    const result = await doLogin(username, password);
    btn.disabled = false;
    if (result.ok) location.href = next;
    else { showTab('login'); setError(loginForm, 'Акаўнт створаны. Увайдзіце са сваім паролем.'); }
  });
})();
