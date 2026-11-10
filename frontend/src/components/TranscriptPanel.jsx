import React from 'react';
import { FileText, CheckCircle2, Languages, Cpu, Timer } from 'lucide-react';

export default function TranscriptPanel({
  transcript,
  detectedLanguage,
  confidence,
  modelName = 'prisma-v3.0',
  processingTimeMs,
  isProcessing = false,
}) {
  if (!transcript && !isProcessing) {
    return (
      <div className="p-4 rounded-2xl glass-card text-center text-slate-500 text-xs flex items-center justify-center gap-2">
        <FileText className="w-4 h-4 opacity-50" />
        <span>Live transcript and language detection will appear here after speaking.</span>
      </div>
    );
  }

  return (
    <div className="p-4 rounded-2xl glass-panel space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-violet-400" />
          <span className="font-semibold uppercase tracking-wider text-slate-300">
            Gnani Prisma STT Output
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {detectedLanguage && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-950/60 border border-violet-700/50 text-violet-300 font-mono text-[11px]">
              <Languages className="w-3 h-3" />
              {detectedLanguage}
            </span>
          )}
          {confidence !== undefined && confidence !== null && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-700/50 text-emerald-300 font-mono text-[11px]">
              <CheckCircle2 className="w-3 h-3" />
              {Math.round(confidence * 100)}%
            </span>
          )}
          {processingTimeMs !== undefined && processingTimeMs !== null && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-950/60 border border-blue-700/50 text-blue-300 font-mono text-[11px]">
              <Timer className="w-3 h-3" />
              {Math.round(processingTimeMs)} ms
            </span>
          )}
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[10px] font-mono">
            <Cpu className="w-3 h-3" />
            {modelName}
          </span>
        </div>
      </div>

      <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800/80 text-sm text-slate-200 min-h-[50px] leading-relaxed">
        {isProcessing ? (
          <div className="flex items-center gap-2 text-violet-400 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-violet-400 animate-ping" />
            Processing audio with Gnani Prisma...
          </div>
        ) : (
          transcript
        )}
      </div>
    </div>
  );
}
