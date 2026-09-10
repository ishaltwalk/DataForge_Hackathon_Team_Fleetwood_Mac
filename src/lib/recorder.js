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
          noiseSuppression: false,
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
          activeStream?.getTracks().forEach((t) => t.stop());
          try {
            const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
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
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([view], { type: 'audio/wav' });
}
