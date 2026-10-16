(function () {
  const config = window.BETWEENUS_CONFIG || {};
  const dashboardShell = document.querySelector('.dashboard-shell');
  const getCookie = (name) => document.cookie.split('; ').find((row) => row.startsWith(name + '='))?.split('=')[1];
  const csrf = decodeURIComponent(getCookie('csrftoken') || config.csrfToken || '');
  const postJson = async (url, data) => {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' }, body: JSON.stringify(data) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || 'Something went wrong.');
    return body;
  };

  const moodSound = { love: [523.25, 659.25], missing: [392, 329.63], sad: [293.66, 246.94], hug: [349.23, 440], happy: [659.25, 783.99], space: [261.63, 329.63], thinking: [440, 554.37], support: [349.23, 392] };
  const playMoodSound = (moodType) => {
    if (config.soundEnabled === false || !window.AudioContext) return;
    try {
      const context = new AudioContext();
      (moodSound[moodType] || moodSound.love).forEach((frequency, index) => {
        const oscillator = context.createOscillator(); const gain = context.createGain();
        oscillator.type = index ? 'sine' : 'triangle'; oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, context.currentTime + index * 0.09);
        gain.gain.exponentialRampToValueAtTime(0.06, context.currentTime + index * 0.09 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + index * 0.09 + 0.46);
        oscillator.connect(gain); gain.connect(context.destination); oscillator.start(context.currentTime + index * 0.09); oscillator.stop(context.currentTime + index * 0.09 + 0.5);
      });
      setTimeout(() => context.close(), 900);
    } catch (_) { /* Browsers may block audio until a user gesture. */ }
  };
  const vibrate = () => { if (config.vibrationEnabled !== false && navigator.vibrate) navigator.vibrate([100, 50, 100]); };
  const notifyBrowser = (title, body, moodType) => {
    if (config.browserNotificationsEnabled === false || !('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      new Notification(title, {
        body,
        icon: '/static/images/betweenus-logo.svg',
        tag: 'betweenus-feeling',
        silent: config.soundEnabled === false,
        data: { moodType, url: '/dashboard/' }
      });
    } catch (_) { /* Browser notifications can be unavailable in some embedded browsers. */ }
  };

  const registerPush = async (askPermission) => {
    if (!config.vapidPublicKey || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return false;
    const registration = await navigator.serviceWorker.register('/sw.js');
    let permission = Notification.permission;
    if (askPermission && permission === 'default') permission = await Notification.requestPermission();
    if (permission !== 'granted') return false;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      const encodedKey = config.vapidPublicKey.replace(/-/g, '+').replace(/_/g, '/');
      const paddedKey = encodedKey + '='.repeat((4 - encodedKey.length % 4) % 4);
      const key = Uint8Array.from(atob(paddedKey), (char) => char.charCodeAt(0));
      subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    }
    await postJson(config.subscribeUrl, { subscription: subscription.toJSON() }); return true;
  };
  if (config.vapidPublicKey) registerPush(false).catch(() => {});
  document.querySelectorAll('[data-enable-push]').forEach((button) => button.addEventListener('click', async () => {
    const status = document.querySelector('[data-push-status]'); button.disabled = true;
    try { const enabled = await registerPush(true); if (status) status.textContent = enabled ? 'Browser alerts are enabled on this device.' : 'Browser permission was not granted yet.'; }
    catch (_) { if (status) status.textContent = 'Browser alerts need HTTPS and VAPID keys before they can be enabled.'; }
    finally { button.disabled = false; }
  }));

  document.querySelectorAll('[data-copy-target]').forEach((button) => button.addEventListener('click', async () => { const input = document.getElementById(button.dataset.copyTarget); await navigator.clipboard.writeText(input.value); const original = button.textContent; button.textContent = '✓'; setTimeout(() => { button.textContent = original; }, 1500); }));
  document.querySelectorAll('[data-copy-value]').forEach((button) => button.addEventListener('click', async () => { await navigator.clipboard.writeText(button.dataset.copyValue); const original = button.innerHTML; button.innerHTML = 'Link copied <span>✓</span>'; setTimeout(() => { button.innerHTML = original; }, 1800); }));
  document.querySelectorAll('[data-confirm]').forEach((form) => form.addEventListener('submit', (event) => { if (!window.confirm(form.dataset.confirm)) event.preventDefault(); }));

  const feedback = document.querySelector('[data-mood-feedback]');
  const showFeedback = (message, error) => { if (!feedback) return; feedback.textContent = message; feedback.classList.toggle('error', !!error); };
  const pulseButton = (button) => { button.classList.add('selected'); setTimeout(() => button.classList.remove('selected'), 2600); };
  let reloadTimer = null;
  let socketConnected = false;
  let knownPartnerMoodId = dashboardShell?.dataset.partnerMoodId || '';
  const reloadForPartnerUpdate = () => {
    if (reloadTimer) return;
    reloadTimer = setTimeout(() => window.location.reload(), 350);
  };
  const announceMood = (senderId, moodType, moodId) => {
    const button = document.querySelector(`[data-mood="${moodType}"]`); const label = button?.querySelector('span:last-of-type')?.textContent || 'shared a feeling'; const emoji = button?.querySelector('.mood-emoji')?.textContent || '💞';
    if (senderId === config.userId) {
      if (moodId) knownPartnerMoodId = String(moodId);
      showFeedback(`Your person can feel it too — ${label.toLowerCase()} ${emoji}`);
    } else {
      showFeedback(`A new feeling from ${config.partnerName || 'your person'}: ${label} ${emoji}`);
      notifyBrowser(`${config.partnerName || 'Your person'} shared a feeling`, `${label} ${emoji}`, moodType);
      document.querySelector('.person-card-partner')?.classList.add('arrived');
      playMoodSound(moodType); vibrate();
      if (moodId) knownPartnerMoodId = String(moodId);
      setTimeout(() => document.querySelector('.person-card-partner')?.classList.remove('arrived'), 2600);
      reloadForPartnerUpdate();
    }
  };
  document.querySelectorAll('[data-mood]').forEach((button) => button.addEventListener('click', async () => {
    if (!config.moodUrl) return; document.querySelectorAll('[data-mood]').forEach((item) => item.disabled = true);
    try { const result = await postJson(config.moodUrl, { mood_type: button.dataset.mood }); pulseButton(button); playMoodSound(button.dataset.mood); announceMood(config.userId, button.dataset.mood, result.mood?.id); } catch (error) { showFeedback(error.message, true); }
    finally { document.querySelectorAll('[data-mood]').forEach((item) => item.disabled = false); }
  }));
  document.querySelectorAll('[data-reaction]').forEach((button) => button.addEventListener('click', async () => { try { await postJson(config.reactionUrl, { reaction_type: button.dataset.reaction }); button.animate([{ transform:'scale(1)' }, { transform:'scale(1.25) rotate(-8deg)' }, { transform:'scale(1)' }], { duration:400 }); showFeedback(`${button.textContent} sent with love.`); } catch (error) { showFeedback(error.message, true); } }));

  const pollDashboardState = async () => {
    if (!config.stateUrl || socketConnected) return;
    try {
      const response = await fetch(config.stateUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, cache: 'no-store' });
      if (!response.ok) return;
      const state = await response.json();
      const incomingMoodId = state.partner_mood?.id ? String(state.partner_mood.id) : '';
      if (incomingMoodId !== knownPartnerMoodId) {
        if (state.partner_mood) announceMood(config.partnerId, state.partner_mood.type, incomingMoodId);
        else window.location.reload();
      }
    } catch (_) { /* A temporary network failure will be retried on the next interval. */ }
  };

  const connectSocket = () => {
    if (!config.socketUrl) return; let socket; try { socket = new WebSocket(config.socketUrl); } catch (_) { return; }
    socket.addEventListener('open', () => { socketConnected = true; document.querySelector('.live-pill')?.classList.add('connected'); });
    socket.addEventListener('message', (event) => {
      let data; try { data = JSON.parse(event.data); } catch (_) { return; }
      if (data.type === 'mood') announceMood(data.sender_id, data.mood_type, data.mood_id);
      if (data.type === 'reaction' && data.sender_id !== config.userId) { showFeedback('A little something just arrived from your person 💞'); notifyBrowser(`${config.partnerName || 'Your person'} sent a reaction`, 'A little something just arrived 💞', 'reaction'); vibrate(); }
    });
    socket.addEventListener('close', () => { socketConnected = false; document.querySelector('.live-pill')?.classList.remove('connected'); setTimeout(connectSocket, 5000); });
  };
  if (config.socketUrl) connectSocket();
  if (config.stateUrl) setInterval(pollDashboardState, 4000);
})();
