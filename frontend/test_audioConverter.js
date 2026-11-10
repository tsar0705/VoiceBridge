// Test verification for encodeAudioBufferToWav
import { encodeAudioBufferToWav } from './src/utils/audioConverter.js';
import assert from 'assert';

console.log('Testing encodeAudioBufferToWav...');

// Mock AudioBuffer
const sampleRate = 16000;
const duration = 2.0; // 2 seconds
const length = sampleRate * duration;
const channelData = new Float32Array(length);

// Fill with 440Hz sine wave tone
for (let i = 0; i < length; i++) {
  channelData[i] = Math.sin((2 * Math.PI * 440 * i) / sampleRate) * 0.8;
}

const mockAudioBuffer = {
  sampleRate,
  length,
  duration,
  numberOfChannels: 1,
  getChannelData: (ch) => channelData,
};

const wavBuffer = encodeAudioBufferToWav(mockAudioBuffer, 16000);
const bytes = new Uint8Array(wavBuffer);
const view = new DataView(wavBuffer);

// Verify RIFF header
const riff = String.fromCharCode(...bytes.slice(0, 4));
assert.strictEqual(riff, 'RIFF', 'Expected RIFF header');

// Verify WAVE
const wave = String.fromCharCode(...bytes.slice(8, 12));
assert.strictEqual(wave, 'WAVE', 'Expected WAVE header');

// Verify "fmt "
const fmt = String.fromCharCode(...bytes.slice(12, 16));
assert.strictEqual(fmt, 'fmt ', 'Expected fmt chunk');

// Verify PCM format = 1
const format = view.getUint16(20, true);
assert.strictEqual(format, 1, 'Expected PCM format (1)');

// Verify Mono = 1
const channels = view.getUint16(22, true);
assert.strictEqual(channels, 1, 'Expected 1 channel (mono)');

// Verify Sample Rate = 16000
const sRate = view.getUint32(24, true);
assert.strictEqual(sRate, 16000, 'Expected 16000 Hz');

// Verify BitsPerSample = 16
const bitsPerSample = view.getUint16(34, true);
assert.strictEqual(bitsPerSample, 16, 'Expected 16 bits per sample');

// Verify "data"
const dataStr = String.fromCharCode(...bytes.slice(36, 40));
assert.strictEqual(dataStr, 'data', 'Expected data chunk header');

// Verify total length = 44 + (length * 2)
const expectedTotal = 44 + length * 2;
assert.strictEqual(wavBuffer.byteLength, expectedTotal, `Expected ${expectedTotal} bytes, got ${wavBuffer.byteLength}`);

console.log(`PASSED: Generated valid 16-bit PCM WAV (${wavBuffer.byteLength} bytes, ${sRate} Hz, mono)`);
