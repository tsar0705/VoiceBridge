import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, Volume2, RotateCcw } from 'lucide-react';

export default function AudioPlayer({ audioUrl, audioBase64, mimeType = 'audio/wav', label = 'AI Response Audio' }) {
  const audioRef = useRef(null);
  const [objectUrl, setObjectUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);

  // Convert Base64 to Blob URL and clean up with revokeObjectURL
  useEffect(() => {
    if (audioUrl) {
      setObjectUrl(audioUrl);
      return;
    }

    if (audioBase64) {
      try {
        const byteCharacters = atob(audioBase64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: mimeType || 'audio/wav' });
        const createdUrl = URL.createObjectURL(blob);
        setObjectUrl(createdUrl);

        return () => {
          URL.revokeObjectURL(createdUrl);
        };
      } catch (err) {
        console.error('Failed to create audio object URL:', err);
      }
    } else {
      setObjectUrl(null);
    }
  }, [audioBase64, audioUrl, mimeType]);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => console.error('Audio playback error:', err));
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const cur = audioRef.current.currentTime;
      const total = audioRef.current.duration || 1;
      setCurrentTime(cur);
      setProgress((cur / total) * 100);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      const dur = audioRef.current.duration;
      if (dur && !isNaN(dur) && isFinite(dur)) {
        setDuration(dur);
      }
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setProgress(0);
    setCurrentTime(0);
  };

  const handleSeek = (e) => {
    if (!audioRef.current) return;
    const seekVal = parseFloat(e.target.value);
    const seekTime = (seekVal / 100) * (audioRef.current.duration || 0);
    audioRef.current.currentTime = seekTime;
    setProgress(seekVal);
  };

  const cycleSpeed = () => {
    const speeds = [1.0, 1.25, 1.5, 0.85];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    setPlaybackSpeed(speeds[nextIdx]);
  };

  const formatSec = (s) => {
    if (!s || isNaN(s)) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  if (!objectUrl) return null;

  return (
    <div className="flex items-center gap-3 p-3 rounded-2xl glass-card text-xs">
      <audio
        ref={audioRef}
        src={objectUrl}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />

      <button
        onClick={togglePlay}
        className="w-9 h-9 rounded-full bg-gradient-to-tr from-violet-600 to-blue-500 hover:from-violet-500 hover:to-blue-400 text-white flex items-center justify-center shrink-0 transition-transform active:scale-95 shadow-md shadow-violet-900/40"
        title={isPlaying ? 'Pause' : 'Play audio'}
        aria-label={isPlaying ? 'Pause audio' : 'Play audio'}
      >
        {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 ml-0.5 fill-white" />}
      </button>

      <div className="flex-1 flex flex-col gap-1.5 min-w-0">
        <div className="flex justify-between items-center text-slate-400 font-mono text-[11px]">
          <span className="flex items-center gap-1.5 font-sans text-slate-200 font-medium truncate">
            <Volume2 className="w-3.5 h-3.5 text-violet-400 shrink-0" />
            {label}
          </span>
          <span className="shrink-0 text-slate-400">
            {formatSec(currentTime)} / {duration > 0 ? formatSec(duration) : '...'}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="100"
          step="0.1"
          value={progress}
          onChange={handleSeek}
          aria-label="Seek audio playback"
          className="w-full h-1.5 bg-slate-700/80 rounded-lg appearance-none cursor-pointer accent-violet-400"
        />
      </div>

      <button
        onClick={cycleSpeed}
        className="px-2.5 py-1 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-300 font-mono font-bold text-[10px] transition-colors shrink-0 border border-slate-700/50"
        title="Cycle playback speed (1x, 1.25x, 1.5x, 0.85x)"
      >
        {playbackSpeed}x
      </button>
    </div>
  );
}
