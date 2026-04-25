import { useState, useEffect, useRef } from 'react';
import { UploadZone } from './components/UploadZone';
import { ProgressBar } from './components/ProgressBar';
import { ResultViewer } from './components/ResultViewer';
import { HistoryList } from './components/HistoryList';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Moon, Sun, Languages } from 'lucide-react';
import * as api from './services/api';
import './styles/index.css';

export interface JobState {
  id: string;
  status: 'idle' | 'uploading' | 'analyzing' | 'transcribing' | 'converting' | 'ready' | 'error';
  progress: number;
  message: string;
  result?: {
    musicxml: string;
    midi: string;
    log: string;
    pdf?: string;
  };
}

export const App = () => {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [lang, setLang] = useState<'pt' | 'en'>('pt');

  const [job, setJob] = useState<JobState>({
    id: '',
    status: 'idle',
    progress: 0,
    message: ''
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light');
  const toggleLang = () => setLang(l => l === 'pt' ? 'en' : 'pt');

  // Ref to hold WebSocket cleanup function
  const wsCleanupRef = useRef<(() => void) | null>(null);

  const handleUpload = async (file: File, timeSignature: string, audioType: string) => {
    try {
      // Cleanup any previous WebSocket subscription
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
        wsCleanupRef.current = null;
      }
      setJob({ id: '', status: 'uploading', progress: 0, message: 'Uploading audio to server...' });
      const { job_id } = await api.uploadAudio(file, timeSignature, audioType);
      setJob(prev => ({ ...prev, id: job_id, status: 'uploading', progress: 20 }));
      subscribeToStatus(job_id);
    } catch (err: any) {
      setJob(prev => ({ ...prev, status: 'error', message: err.message || 'Upload failed' }));
    }
  };

  const subscribeToStatus = (jobId: string) => {
    const cleanup = api.subscribeJobStatus(jobId, async (data) => {
      if (data.status === 'ready') {
        try {
          const result = await api.getJobResult(jobId);
          setJob(prev => ({ ...prev, status: 'ready', progress: 100, message: data.message, result }));
        } catch (e) {
          setJob(prev => ({ ...prev, status: 'error', message: 'Failed to load result.' }));
        }
      } else {
        setJob(prev => ({
          ...prev,
          status: data.status as JobState['status'],
          progress: data.progress,
          message: data.message
        }));
      }
    });
    wsCleanupRef.current = cleanup;
  };

  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    // Load history on mount
    api.getHistory().then(setHistory).catch(console.error);
  }, []);

  const handleSelectHistory = async (id: string) => {
    setJob(prev => ({ ...prev, id, status: 'uploading', message: 'Loading from history...', progress: 100 }));
    try {
      const result = await api.getJobResult(id);
      setJob(prev => ({ ...prev, status: 'ready', result }));
    } catch (err) {
      setJob(prev => ({ ...prev, status: 'error', message: 'Failed to load from history.' }));
    }
  };

  const handleDeleteHistory = async (id: string) => {
    try {
      await api.deleteJob(id);
    } catch (err) {
      console.error('Delete failed:', err);
    }
    setHistory(h => h.filter(item => item.id !== id));
  };

  return (
    <div className="app-container" style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontWeight: 600, fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: 'var(--accent)' }}>Score</span>Flow
        </h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button onClick={toggleLang} style={{ background: 'transparent', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <Languages size={18} /> {lang.toUpperCase()}
          </button>
          <button onClick={toggleTheme} style={{ background: 'transparent', color: 'var(--text-secondary)' }}>
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </div>
      </header>

      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {job.status === 'idle' && (
          <>
            <UploadZone onUpload={handleUpload} lang={lang} />
            <HistoryList items={history} onSelect={handleSelectHistory} onDelete={handleDeleteHistory} lang={lang} />
          </>
        )}

        {job.status !== 'idle' && job.status !== 'ready' && (
          <ProgressBar status={job.status} progress={job.progress} message={job.message} lang={lang} />
        )}

        {job.status === 'ready' && job.result && (
          <ErrorBoundary lang={lang}>
            <div className="fade-in">
              <ResultViewer result={job.result} lang={lang} onReset={() => setJob({ id: '', status: 'idle', progress: 0, message: '' })} />
            </div>
          </ErrorBoundary>
        )}
      </main>

    </div>
  );
};
