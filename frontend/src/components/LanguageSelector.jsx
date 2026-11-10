import React from 'react';
import { Globe, Sparkles, Check } from 'lucide-react';

const INPUT_LANGUAGES = [
  { id: 'indic-auto', label: 'Auto Detect (Indic Auto)' },
  { id: 'codemix', label: 'Code-Mixed (Tanglish / Hinglish)' },
  { id: 'ta', label: 'Tamil' },
  { id: 'en', label: 'English' },
  { id: 'hi', label: 'Hindi' },
];

const RESPONSE_LANGUAGES = [
  { id: 'auto', label: 'Auto (Follow Spoken Language)' },
  { id: 'Tamil', label: 'Tamil (தமிழ்)' },
  { id: 'English', label: 'English (Indian Accent)' },
  { id: 'Hindi', label: 'Hindi (हिन्दी)' },
  { id: 'Tanglish', label: 'Tanglish (Tamil + English)' },
  { id: 'Hinglish', label: 'Hinglish (Hindi + English)' },
];

export default function LanguageSelector({
  inputLanguage,
  setInputLanguage,
  responseLanguage,
  setResponseLanguage,
  codeMixEnabled,
  setCodeMixEnabled,
}) {
  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl glass-panel">
      {/* Input Speech Mode */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center shrink-0">
          <Globe className="w-4 h-4 text-violet-400" />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Speech Recognition Mode
          </label>
          <select
            value={inputLanguage}
            onChange={(e) => setInputLanguage(e.target.value)}
            aria-label="Select Input Speech Recognition Mode"
            className="bg-slate-900/80 border border-slate-700/60 rounded-xl px-2.5 py-1 text-xs font-medium text-slate-200 focus:outline-none focus:ring-2 focus:ring-violet-500 transition-all cursor-pointer mt-0.5"
          >
            {INPUT_LANGUAGES.map((lang) => (
              <option key={lang.id} value={lang.id}>
                {lang.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Response Spoken Language */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0">
          <Sparkles className="w-4 h-4 text-blue-400" />
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Spoken Response Language
          </label>
          <select
            value={responseLanguage}
            onChange={(e) => setResponseLanguage(e.target.value)}
            aria-label="Select AI Spoken Response Language"
            className="bg-slate-900/80 border border-slate-700/60 rounded-xl px-2.5 py-1 text-xs font-medium text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all cursor-pointer mt-0.5"
          >
            {RESPONSE_LANGUAGES.map((lang) => (
              <option key={lang.id} value={lang.id}>
                {lang.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
