import React, { useState, useEffect } from 'react';
import { Radio, RotateCcw, AlertCircle, ShieldCheck, RefreshCw } from 'lucide-react';
import LanguageSelector from './components/LanguageSelector';
import VoiceRecorder from './components/VoiceRecorder';
import ChatWindow from './components/ChatWindow';
import TranscriptPanel from './components/TranscriptPanel';
import { checkHealth, sendVoiceChat, resetSession } from './services/api';

export default function App() {
  const [backendStatus, setBackendStatus] = useState('checking'); // checking | online | offline
  const [backendInfo, setBackendInfo] = useState(null);
  const [sessionId, setSessionId] = useState(() => 'sess_' + Math.random().toString(36).substring(2, 10));
  
  // Language settings
  const [inputLanguage, setInputLanguage] = useState('indic-auto');
  const [responseLanguage, setResponseLanguage] = useState('auto');
  const [codeMixEnabled, setCodeMixEnabled] = useState(true);

  // Conversation & Transcription state
  const [conversation, setConversation] = useState([]);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [detectedLanguage, setDetectedLanguage] = useState(null);
  const [confidence, setConfidence] = useState(null);
  const [processingTimeMs, setProcessingTimeMs] = useState(null);
  const [models, setModels] = useState({ stt: 'prisma-v3.0', llm: 'gemini-2.5-flash', tts: 'timbre-v2.5' });
  const [isProcessing, setIsProcessing] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  const verifyBackend = async () => {
    setBackendStatus('checking');
    try {
      const res = await checkHealth();
      setBackendStatus('online');
      setBackendInfo(res);
      setErrorMessage(null);
    } catch (err) {
      setBackendStatus('offline');
    }
  };

  // Poll backend health on initial mount
  useEffect(() => {
    verifyBackend();
  }, []);

  const handleResetConversation = async () => {
    if (isResetting || isProcessing) return;
    setIsResetting(true);
    setErrorMessage(null);

    try {
      if (sessionId) {
        await resetSession(sessionId);
      }
    } catch (err) {
      console.warn('Backend session reset warning:', err);
    } finally {
      setConversation([]);
      setCurrentTranscript('');
      setDetectedLanguage(null);
      setConfidence(null);
      setProcessingTimeMs(null);
      setSessionId('sess_' + Math.random().toString(36).substring(2, 10));
      setIsResetting(false);
    }
  };

  const handleAudioRecorded = async (audioBlob) => {
    setIsProcessing(true);
    setErrorMessage(null);

    try {
      const data = await sendVoiceChat(audioBlob, sessionId, responseLanguage);
      
      setCurrentTranscript(data.transcription);
      setDetectedLanguage(data.detected_input_language);
      if (data.processing_time_ms) {
        setProcessingTimeMs(data.processing_time_ms);
      }
      if (data.models) {
        setModels(data.models);
      }

      // Append user and assistant messages to chat
      setConversation((prev) => [
        ...prev,
        {
          role: 'user',
          content: data.transcription,
          language: data.detected_input_language,
        },
        {
          role: 'assistant',
          content: data.ai_response_text,
          language: data.output_language,
          audioBase64: data.audio_base64,
          audioUrl: data.audio_url,
          audioMime: data.audio_format,
        },
      ]);
    } catch (err) {
      console.error('Voice interaction failed:', err);
      setErrorMessage(err.message || 'Failed to complete voice interaction.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between p-4 md:p-8 max-w-5xl mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between pb-6 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-violet-600 to-blue-500 flex items-center justify-center text-white shadow-lg shadow-violet-900/40">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white">VoiceBridge</h1>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-violet-950/80 border border-violet-700/60 text-violet-300">
                MVP v0.1
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Multilingual Indian AI Voice Assistant &bull; Powered by Gnani AI
            </p>
          </div>
        </div>

        {/* Status & Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={verifyBackend}
            type="button"
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border cursor-pointer transition-all ${
              backendStatus === 'online'
                ? 'bg-emerald-950/60 border-emerald-700/60 text-emerald-300 hover:bg-emerald-900/60'
                : backendStatus === 'offline'
                ? 'bg-rose-950/60 border-rose-700/60 text-rose-300 hover:bg-rose-900/60'
                : 'bg-amber-950/60 border-amber-700/60 text-amber-300'
            }`}
            title="Click to check backend health status"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                backendStatus === 'online'
                  ? 'bg-emerald-400 animate-pulse'
                  : backendStatus === 'offline'
                  ? 'bg-rose-500'
                  : 'bg-amber-400 animate-ping'
              }`}
            />
            <span className="capitalize">{backendStatus === 'online' ? 'Backend Ready' : backendStatus}</span>
            {backendStatus === 'offline' && <RefreshCw className="w-3 h-3 ml-0.5" />}
          </button>

          <button
            onClick={handleResetConversation}
            disabled={isResetting || isProcessing}
            type="button"
            className="p-2 rounded-xl glass-card hover:bg-slate-800 text-slate-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
            title="Reset Conversation (Clears backend session)"
            aria-label="Reset Conversation"
          >
            <RotateCcw className={`w-4 h-4 ${isResetting ? 'animate-spin text-violet-400' : ''}`} />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 py-6 flex flex-col gap-6">
        {/* Language Controls */}
        <LanguageSelector
          inputLanguage={inputLanguage}
          setInputLanguage={setInputLanguage}
          responseLanguage={responseLanguage}
          setResponseLanguage={setResponseLanguage}
          codeMixEnabled={codeMixEnabled}
          setCodeMixEnabled={setCodeMixEnabled}
        />

        {/* Global Error Notice if any */}
        {errorMessage && (
          <div className="flex items-center gap-2 p-3 rounded-2xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Conversation History Window */}
        <ChatWindow conversation={conversation} isProcessing={isProcessing} />

        {/* Live / Recent Transcription Feedback */}
        <TranscriptPanel
          transcript={currentTranscript}
          detectedLanguage={detectedLanguage}
          confidence={confidence}
          modelName={models.stt}
          processingTimeMs={processingTimeMs}
          isProcessing={isProcessing}
        />

        {/* Voice Recorder & Audio Pipeline Trigger */}
        <VoiceRecorder
          onAudioRecorded={handleAudioRecorded}
          isProcessing={isProcessing}
          disabled={backendStatus === 'offline'}
        />
      </main>

      {/* Footer */}
      <footer className="pt-4 border-t border-slate-800/80 text-center text-xs text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-violet-400" />
          <span>The Great Indian AI Internship Challenge &bull; Gnani AI</span>
        </div>
        <div>
          <span>Models: Gnani Prisma ({models.stt}) + Modular LLM ({models.llm}) + Gnani Timbre ({models.tts})</span>
        </div>
      </footer>
    </div>
  );
}
