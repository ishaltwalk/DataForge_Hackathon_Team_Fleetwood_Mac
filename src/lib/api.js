const CLIENT_KEY = 'echocoach-client-id';

export function clientId() {
  let id = localStorage.getItem(CLIENT_KEY);
  if (!id) {
    id = (crypto.randomUUID?.() || String(Math.random()).slice(2)) + '';
    localStorage.setItem(CLIENT_KEY, id);
  }
  return id;
}

async function get(path) {
  const res = await fetch(path, { headers: { 'X-Client-Id': clientId() } });
  if (!res.ok) {
    throw new Error(await errorText(res));
  }
  return res.json();
}

async function errorText(res) {
  try {
    const body = await res.json();
    return body.error || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export function getConfig() {
  return get('/api/config');
}

export function getWords(query = '', limit = 60) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (query) params.set('q', query);
  return get(`/api/words?${params.toString()}`);
}

export function getWord(wordId) {
  return get(`/api/words/${encodeURIComponent(wordId)}`);
}

export function getPrompt(wordId) {
  return get(`/api/prompt/${encodeURIComponent(wordId)}`);
}

export async function submitAttempt(wordId, wavBlob) {
  const form = new FormData();
  form.append('word_id', wordId);
  form.append('client_id', clientId());
  form.append('audio', wavBlob, 'attempt.wav');

  const res = await fetch('/api/attempt', {
    method: 'POST',
    body: form,
    headers: { 'X-Client-Id': clientId() },
  });
  if (!res.ok) {
    throw new Error(await errorText(res));
  }
  return res.json();
}

export function speakFallback(text, { onEnd, onError } = {}) {
  if (!('speechSynthesis' in window)) {
    onError?.(new Error('This browser has no speech synthesis.'));
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.75;
  utterance.onend = () => onEnd?.();
  utterance.onerror = (e) => onError?.(e.error || new Error('Playback failed'));
  window.speechSynthesis.speak(utterance);
}
