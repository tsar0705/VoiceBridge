/**
 * VoiceBridge Audio Format Converter
 * Converts browser MediaRecorder audio (e.g. WebM/Opus or Ogg/Opus) into a
 * genuine 16-bit mono PCM WAV (RIFF/WAVE) file suitable for Gnani Prisma STT.
 */

/**
 * Encodes an AudioBuffer into a standard 16-bit PCM WAV ArrayBuffer.
 * 
 * @param {AudioBuffer} audioBuffer - Decoded Web Audio AudioBuffer
 * @param {number} sampleRate - Target sample rate in Hz (e.g., 16000)
 * @returns {ArrayBuffer} - Standard RIFF WAV binary buffer
 */
export function encodeAudioBufferToWav(audioBuffer, sampleRate = 16000) {
  const numChannels = 1; // Downmix to Mono for optimal speech recognition
  const bytesPerSample = 2; // 16-bit PCM
  const blockAlign = numChannels * bytesPerSample; // 2 bytes per block

  // Extract and downmix channels to mono
  const numInputChannels = audioBuffer.numberOfChannels;
  const numSamples = audioBuffer.length;
  const monoChannel = new Float32Array(numSamples);

  if (numInputChannels === 1) {
    monoChannel.set(audioBuffer.getChannelData(0));
  } else {
    // Average all input channels
    for (let c = 0; c < numInputChannels; c++) {
      const channelData = audioBuffer.getChannelData(c);
      for (let i = 0; i < numSamples; i++) {
        monoChannel[i] += channelData[i] / numInputChannels;
      }
    }
  }

  const dataByteLength = numSamples * bytesPerSample;
  const headerByteLength = 44;
  const totalLength = headerByteLength + dataByteLength;

  const buffer = new ArrayBuffer(totalLength);
  const view = new DataView(buffer);

  function writeString(offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  // 1. RIFF Chunk Descriptor
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataByteLength, true); // ChunkSize = 36 + SubChunk2Size
  writeString(8, 'WAVE');

  // 2. "fmt " Sub-chunk
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size for PCM (16 bytes)
  view.setUint16(20, 1, true); // AudioFormat: 1 = Linear PCM
  view.setUint16(22, numChannels, true); // NumChannels = 1 (Mono)
  view.setUint32(24, sampleRate, true); // SampleRate (e.g., 16000)
  view.setUint32(28, sampleRate * blockAlign, true); // ByteRate = SampleRate * BlockAlign
  view.setUint16(32, blockAlign, true); // BlockAlign = NumChannels * BitsPerSample / 8
  view.setUint16(34, 16, true); // BitsPerSample = 16

  // 3. "data" Sub-chunk
  writeString(36, 'data');
  view.setUint32(40, dataByteLength, true); // Subchunk2Size

  // 4. Write 16-bit signed PCM audio samples (Little-Endian)
  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    // Clamp float value to [-1.0, 1.0]
    const s = Math.max(-1, Math.min(1, monoChannel[i]));
    // Scale to 16-bit signed integer range [-32768, 32767]
    const pcm = s < 0 ? s * 0x8000 : s * 0x7FFF;
    view.setInt16(offset, Math.round(pcm), true);
    offset += 2;
  }

  return buffer;
}

/**
 * Converts any browser MediaRecorder Blob (WebM/Opus, Ogg, etc.) into a
 * genuine 16-bit mono PCM WAV Blob.
 * 
 * @param {Blob} rawBlob - Recorded audio Blob from MediaRecorder
 * @param {number} targetSampleRate - Desired sample rate (default 16000 Hz for STT)
 * @returns {Promise<Blob>} - Converted genuine WAV Blob with MIME 'audio/wav'
 */
export async function convertBlobToWav(rawBlob, targetSampleRate = 16000) {
  if (!rawBlob || rawBlob.size === 0) {
    throw new Error('Recorded audio blob is empty.');
  }

  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    throw new Error('Web Audio API AudioContext is not supported by this browser.');
  }

  const audioCtx = new AudioContextClass();

  try {
    const arrayBuffer = await rawBlob.arrayBuffer();
    const decodedAudioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

    // Resample to targetSampleRate and mono using OfflineAudioContext if available
    let resampledBuffer = decodedAudioBuffer;
    const OfflineContextClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;

    if (OfflineContextClass) {
      const targetDuration = decodedAudioBuffer.duration;
      const targetLength = Math.max(1, Math.round(targetDuration * targetSampleRate));
      const offlineCtx = new OfflineContextClass(1, targetLength, targetSampleRate);

      const source = offlineCtx.createBufferSource();
      source.buffer = decodedAudioBuffer;
      source.connect(offlineCtx.destination);
      source.start(0);

      resampledBuffer = await offlineCtx.startRendering();
    }

    const wavArrayBuffer = encodeAudioBufferToWav(resampledBuffer, targetSampleRate);
    return new Blob([wavArrayBuffer], { type: 'audio/wav' });
  } finally {
    if (audioCtx.state !== 'closed') {
      audioCtx.close().catch(() => {});
    }
  }
}
