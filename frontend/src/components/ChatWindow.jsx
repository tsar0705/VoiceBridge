import React, { useState } from 'react';
import { User, Bot, Sparkles, Copy, Check } from 'lucide-react';
import AudioPlayer from './AudioPlayer';

const STARTER_PROMPTS = [
  'Vanakkam! Innaiku weather epdi iruku?',
  'Namaste! Mujhe Bangalore ke baare mein batao',
  "Tell me about Gnani AI's voice models",
];

export default function ChatWindow({ conversation = [], isProcessing = false }) {
  const [copiedPrompt, setCopiedPrompt] = useState(null);

  const handleCopyPrompt = (promptText) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(promptText);
    }
    setCopiedPrompt(promptText);
    setTimeout(() => {
      setCopiedPrompt(null);
    }, 2500);
  };

  if (conversation.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 rounded-3xl glass-panel text-center min-h-[320px]">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600/30 to-blue-500/30 border border-violet-500/30 flex items-center justify-center mb-4 text-violet-400">
          <Sparkles className="w-7 h-7" />
        </div>
        <h3 className="text-lg font-semibold text-slate-200 mb-1">
          Start a Multilingual Voice Conversation
        </h3>
        <p className="text-xs text-slate-400 max-w-sm mb-6 leading-relaxed">
          Speak in Tamil, English, Hindi, Tanglish or Hinglish. VoiceBridge transcribes via Gnani Prisma, reasons with an LLM, and speaks back via Gnani Timbre.
        </p>
        <div className="flex flex-col items-center gap-2 max-w-md w-full">
          <span className="text-[11px] font-medium text-slate-400">
            Click a starter prompt to copy & speak into mic:
          </span>
          <div className="flex flex-wrap gap-2 justify-center">
            {STARTER_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => handleCopyPrompt(prompt)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 hover:border-violet-500/50 text-slate-300 hover:text-white text-xs transition-all cursor-pointer group"
                title="Click to copy suggestion"
              >
                {copiedPrompt === prompt ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3 h-3 text-slate-500 group-hover:text-violet-400 transition-colors" />
                )}
                <span>"{prompt}"</span>
              </button>
            ))}
          </div>
          {copiedPrompt && (
            <span className="text-[11px] text-emerald-400 font-medium animate-pulse mt-1">
              Copied to clipboard! Press the microphone button below to speak it.
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col gap-4 overflow-y-auto p-4 rounded-3xl glass-panel max-h-[460px]">
      {conversation.map((turn, index) => {
        const isUser = turn.role === 'user';
        return (
          <div
            key={index}
            className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs ${
                isUser
                  ? 'bg-blue-600/30 border border-blue-500/40 text-blue-300'
                  : 'bg-violet-600/30 border border-violet-500/40 text-violet-300'
              }`}
            >
              {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[80%] rounded-2xl p-4 space-y-2 ${
                isUser
                  ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100'
                  : 'bg-slate-900/80 border border-violet-500/20 text-slate-100 shadow-lg'
              }`}
            >
              <div className="flex items-center justify-between gap-4 text-[10px] text-slate-400 font-mono">
                <span className="font-sans font-semibold uppercase tracking-wider text-slate-300">
                  {isUser ? 'You' : 'VoiceBridge AI'}
                </span>
                {turn.language && (
                  <span className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
                    {turn.language}
                  </span>
                )}
              </div>

              <p className="text-sm leading-relaxed">{turn.content}</p>

              {/* Audio Player for AI responses */}
              {!isUser && (turn.audioBase64 || turn.audioUrl) && (
                <div className="pt-2">
                  <AudioPlayer
                    audioUrl={turn.audioUrl}
                    audioBase64={turn.audioBase64}
                    mimeType={turn.audioMime || 'audio/wav'}
                    label="Voice Response (Gnani Timbre)"
                  />
                </div>
              )}
            </div>
          </div>
        );
      })}

      {isProcessing && (
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-violet-600/30 border border-violet-500/40 text-violet-300 flex items-center justify-center shrink-0">
            <Bot className="w-4 h-4 animate-pulse" />
          </div>
          <div className="rounded-2xl p-3 bg-slate-900/80 border border-violet-500/20 text-xs text-violet-400 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-violet-400 animate-ping" />
            Generating response & synthesizing audio...
          </div>
        </div>
      )}
    </div>
  );
}
