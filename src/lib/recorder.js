/*
 * Microphone capture that hands the server something it can actually open.
 *
 * THE BUG THIS FILE EXISTS TO FIX
 * ------------------------------
 * The first version uploaded the raw MediaRecorder Blob, which in Chrome is
 * webm/opus. The server scores with librosa, which opens WAV and FLAC through
 * soundfile and needs an external ffmpeg for anything else. On a machine
 * without ffmpeg every single attempt failed to decode; on a machine with it,
 * scoring silently depended on a binary nobody had listed as a dependency.
 *
 * So the conversion happens here instead. The browser already has an Opus
 * decoder (decodeAudioData), and an OfflineAudioContext resamples to the
 * exact 16 kHz mono the wav2vec2 model wants. What leaves this file is a
 * plain 16-bit PCM WAV, which soundfile opens with no extra dependency, and
 * the resample the model needs has already happened rather than being redone
 * server side on audio that lost quality getting there.
 */

const TARGET_RATE = 16000;

export function createRecorder() {
  let mediaRecorder = null;
  let stream = null;
  let chunks = [];

  return {
    async start() {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: false, // it eats fricatives, which are the traps
          autoGainControl: true,
        },
      });
      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      mediaRecorder.start();
    },

    stop() {
      return new Promise((resolve, reject) => {
        if (!mediaRecorder) {
          return reject(new Error('Recorder was not started'));
        }
        const recorder = mediaRecorder;
        const activeStream = stream;
        recorder.onerror = (e) => {
          activeStream?.getTracks().forEach((t) => t.stop());
          reject(e.error || new Error('Recording failed'));
        };
        recorder.onstop = async () => {
          // Tracks are stopped in onstop, not immediately after stop().
          // Killing them first truncates the tail of the word, which on a
          // word like "clothes" is exactly the sound being tested.
          activeStream?.getTracks().forEach((t) => t.stop());
          try {
            const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
            // Both sizes, because they fail differently. A zero-byte captured
            // blob is a microphone problem. A healthy capture that produces a
            // tiny wav is a conversion problem. Guessing between those two
            // wastes more time than one console line costs.
            const wav = await toWav16k(blob);
            console.log(
              `[recorder] captured ${blob.size} bytes (${recorder.mimeType}), ` +
                `converted to ${wav.size} bytes of 16 kHz wav`,
            );
            if (blob.size === 0) {
              throw new Error('The microphone produced no audio at all.');
            }
            resolve(wav);
          } catch (err) {
            reject(err);
          }
        };
        recorder.stop();
        mediaRecorder = null;
        stream = null;
      });
    },

    cancel() {
      try {
        mediaRecorder?.stop();
      } catch {
        /* already stopped */
      }
      stream?.getTracks().forEach((t) => t.stop());
      mediaRecorder = null;
      stream = null;
      chunks = [];
    },
  };
}

export async function toWav16k(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  if (arrayBuffer.byteLength === 0) {
    throw new Error('Empty recording');
  }

  const Ctx = window.AudioContext || window.webkitAudioContext;
  const decodeCtx = new Ctx();
  let decoded;
  try {
    decoded = await decodeCtx.decodeAudioData(arrayBuffer.slice(0));
  } finally {
    decodeCtx.close();
  }

  const frames = Math.max(1, Math.ceil(decoded.duration * TARGET_RATE));
  const offline = new OfflineAudioContext(1, frames, TARGET_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const resampled = await offline.startRendering();

  return encodeWav(resampled.getChannelData(0), TARGET_RATE);
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeText = (offset, text) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };

  writeText(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, 'WAVE');
  writeText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeText(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    // Clamp before scaling. An unclamped sample above 1.0 wraps around and a
    // loud speaker comes back as a burst of noise the ASR reads as garbage.
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}
