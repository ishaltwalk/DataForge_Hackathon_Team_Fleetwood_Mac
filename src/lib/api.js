/*
 * Every call to the Python server goes through here.
 *
 * Paths are relative: Vite proxies /api to port 8000 in dev (vite.config.js),
 * so the browser sees one origin and there is no CORS in the judged path. The
 * hardcoded http://localhost:8000 that used to be in here broke the moment
 * the app was opened from anything other than the dev machine.
 *
 * The word bank is NOT bundled. It is 3.3 MB, and a bundled copy can drift
 * from the copy the server scores against, which produces the worst class of
 * bug here: the screen showing a different word to the one being scored.
 */

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

/*
 * Degraded fallback, and it is labelled as degraded everywhere it is offered.
 *
 * The browser voice cannot speak an RPA string, so it can only read the plain
 * word and guess at the pronunciation. For a word bank chosen for words that
 * TTS engines get wrong, that guess may be the mispronunciation the learner
 * is trying to fix. It is here so a Rime outage does not leave a dead button
 * during a demo, never as a silent substitute: the UI states which provider
 * spoke, every time. See core/speech.py for the server side of this.
 */
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
