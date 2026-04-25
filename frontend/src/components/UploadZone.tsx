import React, { useCallback, useState, useRef, useMemo } from 'react';
import { UploadCloud, Play, Pause, X, Music } from 'lucide-react';

const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
};

export const UploadZone = ({ onUpload, lang }: { onUpload: (f: File, ts: string, type: string) => void, lang: 'pt' | 'en' }) => {
    const [isHover, setIsHover] = useState(false);
    const [error, setError] = useState('');
    const [timeSignature, setTimeSignature] = useState('auto');
    const [audioType, setAudioType] = useState('piano');

    // Audio preview state
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const audioRef = useRef<HTMLAudioElement>(null);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsHover(false);
        const files = e.dataTransfer.files;
        handleFiles(files);
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) handleFiles(e.target.files);
    };

    const handleFiles = (files: FileList) => {
        setError('');
        if (files.length === 0) return;
        if (files.length > 1) {
            setError(lang === 'pt' ? 'Envie apenas um arquivo por vez.' : 'Please upload one file at a time.');
            return;
        }

        const file = files[0];
        const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/wave'];
        const isMp3Wav = file.name.endsWith('.mp3') || file.name.endsWith('.wav') || validTypes.includes(file.type);

        if (!isMp3Wav) {
            setError(lang === 'pt' ? 'Formato não suportado. Envie MP3 ou WAV.' : 'Unsupported format. Please upload MP3 or WAV.');
            return;
        }
        if (file.size > 200 * 1024 * 1024) {
            setError(lang === 'pt' ? 'Arquivo excede limite de 200MB.' : 'File exceeds 200MB limit.');
            return;
        }

        // Set file for preview instead of uploading immediately
        setSelectedFile(file);
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(URL.createObjectURL(file));
        setCurrentTime(0);
        setIsPlaying(false);
    };

    const handleClearFile = () => {
        setSelectedFile(null);
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(null);
        setIsPlaying(false);
        setDuration(0);
        setCurrentTime(0);
        // Reset file input
        const input = document.getElementById('file-upload') as HTMLInputElement;
        if (input) input.value = '';
    };

    const togglePlay = () => {
        if (!audioRef.current) return;
        if (isPlaying) {
            audioRef.current.pause();
        } else {
            audioRef.current.play();
        }
        setIsPlaying(!isPlaying);
    };

    const handleSubmit = () => {
        if (selectedFile) {
            onUpload(selectedFile, timeSignature, audioType);
        }
    };

    const selectStyle = useMemo(() => ({
        padding: '0.5rem 1rem',
        borderRadius: '8px',
        border: '1px solid var(--border)',
        background: 'var(--card-bg)',
        color: 'var(--text-primary)',
        fontSize: '1rem',
        cursor: 'pointer',
        maxWidth: '300px',
        width: '100%',
        outline: 'none',
    }), []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', alignItems: 'center', width: '100%' }}>

            {/* Settings selectors */}
            <div className="upload-settings" style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'center' }}>
                <label htmlFor="audio-type" style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                    {lang === 'pt' ? 'O que você está enviando?' : 'What are you uploading?'}
                </label>
                <select id="audio-type" value={audioType} onChange={(e) => setAudioType(e.target.value)} style={{ ...selectStyle, marginBottom: '1rem' }}>
                    <option value="piano">{lang === 'pt' ? '🎹 Piano ou Banda (Múltiplas Notas)' : '🎹 Piano or Band (Polyphonic)'}</option>
                    <option value="vocal">{lang === 'pt' ? '🎙️ Voz ou Solo (Melodia Simples)' : '🎙️ Vocals or Solo (Monophonic)'}</option>
                </select>

                <label htmlFor="time-signature" style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                    {lang === 'pt' ? 'Fórmula de Compasso da Música:' : 'Song Time Signature:'}
                </label>
                <select id="time-signature" value={timeSignature} onChange={(e) => setTimeSignature(e.target.value)} style={selectStyle}>
                    <option value="auto">{lang === 'pt' ? '🔍 Detectar Automaticamente' : '🔍 Auto-detect'}</option>
                    <option value="4/4">4/4 (Padrão / Standard)</option>
                    <option value="3/4">3/4 (Valsa / Waltz)</option>
                    <option value="6/8">6/8</option>
                    <option value="2/4">2/4</option>
                    <option value="12/8">12/8</option>
                    <option value="3/8">3/8</option>
                </select>
            </div>

            {/* Drop zone OR Audio preview */}
            {!selectedFile ? (
                <div
                    className="drop-zone"
                    onDragOver={(e) => { e.preventDefault(); setIsHover(true); }}
                    onDragLeave={() => setIsHover(false)}
                    onDrop={handleDrop}
                    style={{
                        width: '100%',
                        padding: '4rem 2rem',
                        border: `2px dashed ${isHover ? 'var(--accent)' : 'var(--border)'}`,
                        borderRadius: '12px',
                        background: isHover ? 'var(--bg-secondary)' : 'var(--card-bg)',
                        textAlign: 'center',
                        transition: 'all 0.25s ease',
                        cursor: 'pointer'
                    }}
                    onClick={() => document.getElementById('file-upload')?.click()}
                >
                    <UploadCloud size={48} color="var(--accent)" style={{ marginBottom: '1rem' }} />
                    <h3 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>
                        {lang === 'pt' ? 'Arraste seu áudio aqui' : 'Drop your audio here'}
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                        {lang === 'pt' ? 'ou clique para selecionar um arquivo' : 'or click to select a file'}
                    </p>

                    <input
                        id="file-upload"
                        type="file"
                        accept=".mp3,.wav,audio/mpeg,audio/wav"
                        style={{ display: 'none' }}
                        onChange={handleChange}
                    />

                    <button style={{
                        background: 'var(--accent)',
                        color: 'white',
                        padding: '0.75rem 1.5rem',
                        borderRadius: '6px',
                        fontWeight: 500,
                        pointerEvents: 'none'
                    }}>
                        {lang === 'pt' ? 'Selecionar arquivo' : 'Select file'}
                    </button>
                </div>
            ) : (
                /* Audio Preview Card */
                <div className="audio-preview" style={{
                    width: '100%',
                    padding: '1.5rem',
                    borderRadius: '12px',
                    border: '1px solid var(--accent)',
                    background: 'var(--card-bg)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '1rem',
                }}>
                    {/* File info header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{
                            width: '48px', height: '48px', borderRadius: '12px',
                            background: 'var(--accent)', display: 'flex',
                            alignItems: 'center', justifyContent: 'center', flexShrink: 0
                        }}>
                            <Music size={24} color="white" />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: '1rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {selectedFile.name}
                            </div>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                                {formatFileSize(selectedFile.size)}
                                {duration > 0 && ` • ${formatDuration(duration)}`}
                            </div>
                        </div>
                        <button onClick={handleClearFile} style={{
                            background: 'transparent', color: 'var(--text-secondary)',
                            padding: '0.5rem', borderRadius: '8px', flexShrink: 0
                        }} title={lang === 'pt' ? 'Remover' : 'Remove'}>
                            <X size={20} />
                        </button>
                    </div>

                    {/* Audio player */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <button onClick={togglePlay} style={{
                            width: '40px', height: '40px', borderRadius: '50%',
                            background: 'var(--accent)', color: 'white',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexShrink: 0, padding: 0,
                        }}>
                            {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
                        </button>

                        {/* Progress bar */}
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <input
                                type="range"
                                min={0}
                                max={duration || 1}
                                step={0.1}
                                value={currentTime}
                                onChange={(e) => {
                                    const t = parseFloat(e.target.value);
                                    setCurrentTime(t);
                                    if (audioRef.current) audioRef.current.currentTime = t;
                                }}
                                style={{ width: '100%', cursor: 'pointer', accentColor: 'var(--accent)' }}
                            />
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                <span>{formatDuration(currentTime)}</span>
                                <span>{duration > 0 ? formatDuration(duration) : '--:--'}</span>
                            </div>
                        </div>
                    </div>

                    <audio
                        ref={audioRef}
                        src={audioUrl || undefined}
                        onLoadedMetadata={() => { if (audioRef.current) setDuration(audioRef.current.duration); }}
                        onTimeUpdate={() => { if (audioRef.current) setCurrentTime(audioRef.current.currentTime); }}
                        onEnded={() => setIsPlaying(false)}
                    />

                    {/* Hidden file input for re-selection */}
                    <input id="file-upload" type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" style={{ display: 'none' }} onChange={handleChange} />

                    {/* Action buttons */}
                    <div className="preview-actions" style={{ display: 'flex', gap: '0.75rem' }}>
                        <button onClick={() => document.getElementById('file-upload')?.click()} style={{
                            flex: 1, padding: '0.75rem', borderRadius: '8px',
                            background: 'var(--bg-secondary)', color: 'var(--text-primary)',
                            border: '1px solid var(--border)', fontWeight: 500, fontFamily: 'inherit',
                        }}>
                            {lang === 'pt' ? 'Trocar arquivo' : 'Change file'}
                        </button>
                        <button onClick={handleSubmit} style={{
                            flex: 2, padding: '0.75rem', borderRadius: '8px',
                            background: 'var(--accent)', color: 'white',
                            fontWeight: 600, fontFamily: 'inherit',
                            fontSize: '1rem',
                        }}>
                            {lang === 'pt' ? '🚀 Processar Partitura' : '🚀 Process Score'}
                        </button>
                    </div>
                </div>
            )}

            {error ? (
                <p style={{ color: 'var(--error)', fontSize: '0.9rem' }}>{error}</p>
            ) : !selectedFile ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {lang === 'pt' ? 'Máx. 200 MB • MP3 ou WAV' : 'Max 200 MB • MP3 or WAV'}
                </p>
            ) : null}

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '0.5rem', textAlign: 'center' }}>
                {lang === 'pt' ? 'Ao enviar, você concorda que os dados serão excluídos em 7 dias (LGPD).' : 'By uploading, you agree data is deleted in 7 days.'}
            </p>
        </div>
    );
};
