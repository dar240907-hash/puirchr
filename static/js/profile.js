/* Страница кабинета: скидка и уведомления */
(() => {
  'use strict';
  const S = window.Shukai;
  if (!S || !S.requireAuth()) return;
  const D = S.data;

  const profileForm = document.querySelector('[data-profile-form]');
  const notifyForm = document.querySelector('[data-notify-form]');
  const errorBox = profileForm.querySelector('[data-error]');

  const auth = S.store.get() || {};
  const name = auth.username || 'Карыстальнік';
  document.querySelector('[data-username]').textContent = name;
  document.querySelector('[data-avatar]').textContent = name.charAt(0);

  function showError(text) {
    errorBox.textContent = text || '';
    errorBox.hidden = !text;
  }

  async function load() {
    const res = await S.api(D.apiProfile, { auth: 'required' });
    if (res.status === 401) { S.store.set(null); S.requireAuth(); return; }
    if (!res.ok) { showError(S.errorText(res.data, 'Не ўдалося загрузіць профіль.')); return; }
    profileForm.discount_category.value = res.data.discount_category;
    ['notify_push', 'notify_email', 'notify_in_app'].forEach((key) => {
      notifyForm.elements[key].checked = Boolean(res.data[key]);
    });
  }

  async function save(payload, button) {
    showError('');
    button.disabled = true;
    const res = await S.api(D.apiProfile, { method: 'PUT', body: payload, auth: 'required' });
    button.disabled = false;
    if (res.ok) S.toast('Захавана');
    else showError(S.errorText(res.data, 'Не ўдалося захаваць.'));
  }

  profileForm.addEventListener('submit', (e) => {
    e.preventDefault();
    save({ discount_category: profileForm.discount_category.value }, e.submitter || profileForm.querySelector('[type="submit"]'));
  });

  notifyForm.addEventListener('submit', (e) => {
    e.preventDefault();
    save({
      notify_push: notifyForm.elements.notify_push.checked,
      notify_email: notifyForm.elements.notify_email.checked,
      notify_in_app: notifyForm.elements.notify_in_app.checked,
    }, e.submitter || notifyForm.querySelector('[type="submit"]'));
  });

  document.querySelector('[data-logout]').addEventListener('click', S.logout);

  load();
})();
