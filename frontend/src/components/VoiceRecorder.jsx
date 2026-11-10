import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader2, AlertCircle, Volume2 } from 'lucide-react';
import { convertBlobToWav } from '../utils/audioConverter';

export default function VoiceRecorder({ onAudioRecorded, isProcessing = false, disabled = false }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [errorMessage, setErrorMessage] = useState(null);
  const [audioLevels, setAudioLevels] = useState([20, 35, 60, 45, 75, 50, 65, 40, 80, 55, 30, 25]);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);
  const audioContextRef = useRef(null);
  const animationFrameRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  // Automatically enforce Gnani 30-second max duration
  useEffect(() => {
    if (isRecording && recordingDuration >= 30) {
      stopRecording();
    }
  }, [recordingDuration, isRecording]);

  const startRecording = async () => {
    setErrorMessage(null);
    audioChunksRef.current = [];

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMessage('Microphone access is not supported by your current browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Preferred audio container
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : 'audio/webm';

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;

      // Realtime Audio Visualizer
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
          const audioCtx = new AudioContextClass();
          audioContextRef.current = audioCtx;
          const source = audioCtx.createMediaStreamSource(stream);
          const analyser = audioCtx.createAnalyser();
          analyser.fftSize = 32;
          source.connect(analyser);
          const dataArray = new Uint8Array(analyser.frequencyBinCount);

          const updateVisualizer = () => {
            if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== 'recording') return;
            analyser.getByteFrequencyData(dataArray);
            const levels = Array.from(dataArray.slice(0, 12)).map((v) => Math.max(15, Math.min(100, (v / 255) * 100)));
            setAudioLevels(levels);
            animationFrameRef.current = requestAnimationFrame(updateVisualizer);
          };
          updateVisualizer();
        }
      } catch (audioCtxErr) {
        // Fallback visualizer continues
      }

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop audio tracks
        stream.getTracks().forEach((track) => track.stop());

        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
          audioContextRef.current.close().catch(() => {});
        }
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }

        const rawBlob = new Blob(audioChunksRef.current, { type: mimeType });
        if (!rawBlob || rawBlob.size < 100) {
          setErrorMessage('Recording was too short or empty. Please speak clearly into your microphone.');
          setIsRecording(false);
          return;
        }

        setIsConverting(true);
        try {
          // Convert recorded audio (WebM/Opus) into genuine 16-bit PCM WAV (16kHz Mono) for Gnani Prisma
          const wavBlob = await convertBlobToWav(rawBlob, 16000);
          if (!wavBlob || wavBlob.size < 44) {
            setErrorMessage('Audio conversion failed. Please try speaking again.');
            return;
          }
          if (onAudioRecorded) {
            onAudioRecorded(wavBlob);
          }
        } catch (convErr) {
          console.error('PCM WAV conversion failed:', convErr);
          setErrorMessage(`Failed to convert audio to PCM WAV: ${convErr.message || 'Audio error'}`);
        } finally {
          setIsConverting(false);
        }
      };

      mediaRecorder.start(250); // capture 250ms chunks
      setIsRecording(true);
      setRecordingDuration(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access failed:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage('Microphone access was denied. Please allow microphone permissions in your browser bar.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMessage('No microphone device detected on this system.');
      } else {
        setErrorMessage(`Microphone error: ${err.message || 'Unable to record audio.'}`);
      }
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col items-center justify-center p-6 rounded-3xl glass-panel relative overflow-hidden transition-all duration-300">
      {/* Background ambient glow when recording */}
      {isRecording && (
        <div className="absolute inset-0 bg-rose-500/10 blur-3xl pointer-events-none animate-pulse" />
      )}

      {/* Recording Duration / Status Pill */}
      <div className="mb-4 flex items-center gap-2">
        {isRecording ? (
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/20 border border-rose-500/40 text-rose-300 font-mono text-xs shadow-lg shadow-rose-950/40">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
            <span className="font-semibold">Recording: {formatTime(recordingDuration)} / 00:30</span>
          </div>
        ) : isConverting ? (
          <div className="flex items-center gap-2 px-3.5 py-1 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-300 text-xs">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
            <span>Converting audio to 16kHz PCM WAV for Prisma STT...</span>
          </div>
        ) : isProcessing ? (
          <div className="flex items-center gap-2 px-3.5 py-1 rounded-full bg-violet-500/20 border border-violet-500/40 text-violet-300 text-xs">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-violet-400" />
            <span>VoiceBridge is processing your voice...</span>
          </div>
        ) : (
          <span className="text-xs text-slate-400 font-medium">
            Tap the microphone and speak naturally in your language
          </span>
        )}
      </div>

      {/* Dynamic Waveform Visualization */}
      <div className="flex items-center justify-center gap-1.5 h-10 mb-4 px-4">
        {isRecording
          ? audioLevels.map((lvl, i) => (
              <span
                key={i}
                className="w-1.5 bg-gradient-to-t from-rose-500 via-violet-400 to-blue-400 rounded-full transition-all duration-75"
                style={{
                  height: `${lvl}%`,
                  minHeight: '6px',
                }}
              />
            ))
          : (isProcessing || isConverting)
          ? [...Array(12)].map((_, i) => (
              <span
                key={i}
                className="w-1.5 bg-gradient-to-t from-violet-600 to-blue-400 rounded-full animate-wave"
                style={{
                  height: '35%',
                  animationDelay: `${i * 0.12}s`,
                }}
              />
            ))
          : [...Array(12)].map((_, i) => (
              <span
                key={i}
                className="w-1.5 bg-slate-700/60 rounded-full"
                style={{
                  height: `${12 + (i % 4) * 6}px`,
                }}
              />
            ))}
      </div>

      {/* Primary Interaction Button */}
      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={isProcessing || isConverting || disabled}
        className={`w-20 h-20 rounded-full flex items-center justify-center shadow-2xl transition-all duration-300 transform active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${
          isRecording
            ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/60 scale-105 ring-4 ring-rose-500/30 animate-pulse'
            : (isProcessing || isConverting)
            ? 'bg-slate-800 text-violet-400 shadow-none ring-2 ring-violet-500/20'
            : 'bg-gradient-to-tr from-violet-600 via-indigo-600 to-blue-500 hover:from-violet-500 hover:to-blue-400 text-white shadow-violet-900/60 hover:scale-105 ring-2 ring-violet-400/20'
        }`}
        aria-label={isRecording ? 'Stop Recording' : 'Start Recording'}
        title={isRecording ? 'Click to stop and process' : 'Click to start speaking'}
      >
        {(isProcessing || isConverting) ? (
          <Loader2 className="w-8 h-8 animate-spin" />
        ) : isRecording ? (
          <Square className="w-7 h-7 fill-white" />
        ) : (
          <Mic className="w-8 h-8" />
        )}
      </button>

      {/* Status Subtext */}
      <div className="mt-3 text-xs text-slate-400 font-medium">
        {isRecording
          ? 'Click again to send voice turn'
          : isProcessing
          ? 'Prisma STT → LLM Reasoning → Timbre TTS...'
          : 'Ready for speech'}
      </div>

      {/* Error Feedback Display */}
      {errorMessage && (
        <div className="mt-4 flex items-center gap-2 px-3.5 py-2 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs max-w-md text-center">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
