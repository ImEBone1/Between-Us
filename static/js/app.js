(function () {
  const config = window.BETWEENUS_CONFIG || {};
  const getCookie = (name) => document.cookie.split('; ').find((row) => row.startsWith(name + '='))?.split('=')[1];
  const csrf = decodeURIComponent(getCookie('csrftoken') || config.csrfToken || '');
  const postJson = async (url, data) => {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }, body: JSON.stringify(data) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || 'Something went wrong.');
    return body;
  };

  document.querySelectorAll('[data-copy-target]').forEach((button) => button.addEventListener('click', async () => {
    const input = document.getElementById(button.dataset.copyTarget);
    await navigator.clipboard.writeText(input.value);
    const original = button.textContent; button.textContent = '✓';
    setTimeout(() => { button.textContent = original; }, 1500);
  }));
  document.querySelectorAll('[data-copy-value]').forEach((button) => button.addEventListener('click', async () => {
    await navigator.clipboard.writeText(button.dataset.copyValue);
    const original = button.innerHTML; button.innerHTML = 'Link copied <span>✓</span>';
    setTimeout(() => { button.innerHTML = original; }, 1800);
  }));
  document.querySelectorAll('[data-confirm]').forEach((form) => form.addEventListener('submit', (event) => { if (!window.confirm(form.dataset.confirm)) event.preventDefault(); }));

  const feedback = document.querySelector('[data-mood-feedback]');
  const showFeedback = (message, error) => { if (!feedback) return; feedback.textContent = message; feedback.classList.toggle('error', !!error); };
  const pulseButton = (button) => { button.classList.add('selected'); setTimeout(() => button.classList.remove('selected'), 2600); };
  const announceMood = (senderId, moodType) => {
    const button = document.querySelector(`[data-mood="${moodType}"]`);
    const label = button?.querySelector('span:last-of-type')?.textContent || 'shared a feeling';
    if (senderId === config.userId) { showFeedback(`Your person can feel it too — ${label.toLowerCase()} ${button?.querySelector('.mood-emoji')?.textContent || ''}`); }
    else { showFeedback(`A new feeling from your person: ${label} ${button?.querySelector('.mood-emoji')?.textContent || ''}`); document.querySelector('.person-card-partner')?.classList.add('arrived'); setTimeout(() => document.querySelector('.person-card-partner')?.classList.remove('arrived'), 2600); }
  };
  document.querySelectorAll('[data-mood]').forEach((button) => button.addEventListener('click', async () => {
    if (!config.moodUrl) return;
    document.querySelectorAll('[data-mood]').forEach((item) => item.disabled = true);
    try { const result = await postJson(config.moodUrl, { mood_type: button.dataset.mood }); pulseButton(button); announceMood(config.userId, button.dataset.mood); } catch (error) { showFeedback(error.message, true); }
    finally { document.querySelectorAll('[data-mood]').forEach((item) => item.disabled = false); }
  }));
  document.querySelectorAll('[data-reaction]').forEach((button) => button.addEventListener('click', async () => {
    try { await postJson(config.reactionUrl, { reaction_type: button.dataset.reaction }); button.animate([{ transform:'scale(1)' }, { transform:'scale(1.25) rotate(-8deg)' }, { transform:'scale(1)' }], { duration:400 }); showFeedback(`${button.textContent} sent with love.`); } catch (error) { showFeedback(error.message, true); }
  }));

  const connectSocket = () => {
    if (!config.socketUrl) return;
    let socket;
    try { socket = new WebSocket(config.socketUrl); } catch (_) { return; }
    socket.addEventListener('open', () => document.querySelector('.live-pill')?.classList.add('connected'));
    socket.addEventListener('message', (event) => { const data = JSON.parse(event.data); if (data.type === 'mood') announceMood(data.sender_id, data.mood_type); if (data.type === 'reaction' && data.sender_id !== config.userId) showFeedback('A little something just arrived from your person 💞'); });
    socket.addEventListener('close', () => { document.querySelector('.live-pill')?.classList.remove('connected'); setTimeout(connectSocket, 5000); });
  };
  if (config.socketUrl) connectSocket();
})();
