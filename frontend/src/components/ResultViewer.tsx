import { useEffect, useRef, useState } from 'react';
import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay';
import { Download, FileAudio, FileText, RefreshCw, FileDown } from 'lucide-react';
import { getResultUrl } from '../services/api';
import { ErrorBoundary } from './ErrorBoundary';

interface ResultProps {
    result: {
        musicxml: string;
        midi: string;
        log: string;
        pdf?: string;
    };
    lang: 'pt' | 'en';
    onReset: () => void;
}

export const ResultViewer = ({ result, lang, onReset }: ResultProps) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [osmd, setOsmd] = useState<OpenSheetMusicDisplay | null>(null);
    const isLoadedRef = useRef(false);

    useEffect(() => {
        if (containerRef.current && !osmd) {
            try {
                const instance = new OpenSheetMusicDisplay(containerRef.current, {
                    autoResize: false, // Disabling built-in resize to prevent crash on width=0
                    drawTitle: true,
                });
                setOsmd(instance);
            } catch (e) {
                console.error("OSMD Init Error", e);
            }
        }
    }, [containerRef, osmd]);

    useEffect(() => {
        // Attempt to load mock or real musicxml
        if (osmd && result.musicxml !== 'dummy_url') {
            isLoadedRef.current = false;
            const loadAndRender = async () => {
                try {
                    await osmd.load(getResultUrl(result.musicxml));
                    isLoadedRef.current = true;

                    let attempts = 0;
                    const tryRender = () => {
                        if (!containerRef.current) return;

                        // Avoid rendering if container is hidden or initializing layout
                        // This prevents the "SkyBottomLineCalculator: width not > 0" crash
                        if (containerRef.current.clientWidth < 50) {
                            attempts++;
                            if (attempts < 50) {
                                requestAnimationFrame(tryRender);
                            } else {
                                console.warn("OSMD render aborted: container width never initialized.");
                            }
                            return;
                        }

                        try {
                            osmd.render();
                        } catch (renderError) {
                            console.error("OSMD Render Error", renderError);
                        }
                    };

                    // Start rendering attempts
                    requestAnimationFrame(tryRender);
                } catch (e) {
                    console.error("OSMD Load Promise Error", e);
                }
            };

            loadAndRender();
        }
    }, [osmd, result.musicxml]);

    // Handle Resize manually, to prevent OSMD crashing when dimension is 0
    useEffect(() => {
        if (!containerRef.current || !osmd) return;

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                // Ensure the container width is large enough, and the OSMD is loaded
                if (entry.contentRect.width >= 50 && isLoadedRef.current) {
                    try {
                        osmd.render();
                    } catch (e) {
                        console.warn("OSMD manual resize render failed:", e);
                    }
                }
            }
        });

        resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
        };
    }, [osmd]);

    const handleDownload = async (url: string, filename: string) => {
        if (url === 'dummy_url') return;
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error('Network response was not ok');
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(blobUrl);
        } catch (error) {
            console.error('Download failed:', error);
            // Fallback for when fetch fails
            window.open(url, '_blank');
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <div style={{ textAlign: 'center' }}>
                <h2 style={{ fontSize: '1.8rem', marginBottom: '0.5rem' }}>
                    {lang === 'pt' ? 'Sua partitura está pronta!' : 'Your score is ready!'}
                </h2>
                <p style={{ color: 'var(--text-secondary)' }}>
                    {lang === 'pt' ? 'Visualize, baixe ou ajuste o resultado.' : 'Preview, download, or adjust the result.'}
                </p>
            </div>

            <div style={{
                background: '#fff', // Always white for OSMD
                borderRadius: '8px',
                padding: '2rem',
                minHeight: '400px',
                border: '1px solid var(--border)',
                boxShadow: '0 4px 6px rgba(0,0,0,0.05)',
                overflow: 'auto',
                position: 'relative'
            }}>
                <ErrorBoundary lang={lang}>
                    {result.musicxml === 'dummy_url' && (
                        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', color: '#666' }}>
                            Mock Score Preview / OSMD Area
                        </div>
                    )}
                    <div ref={containerRef} style={{ width: '100%' }} />
                </ErrorBoundary>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                <button
                    onClick={() => handleDownload(getResultUrl(result.musicxml), 'score.musicxml')}
                    style={{
                        padding: '1rem', background: 'var(--accent)', color: 'white', border: 'none', cursor: 'pointer',
                        borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                        fontWeight: 600, width: '100%', fontFamily: 'inherit'
                    }}>
                    <Download size={20} />
                    {lang === 'pt' ? 'Baixar MusicXML' : 'Download MusicXML'}
                </button>
                {result.pdf && (
                    <button
                        onClick={() => handleDownload(getResultUrl(result.pdf!), 'score.pdf')}
                        style={{
                            padding: '1rem', background: 'var(--success)', color: 'white', border: 'none', cursor: 'pointer',
                            borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                            fontWeight: 600, width: '100%', fontFamily: 'inherit'
                        }}>
                        <FileDown size={20} />
                        {lang === 'pt' ? 'Baixar PDF' : 'Download PDF'}
                    </button>
                )}
                <button
                    onClick={() => handleDownload(getResultUrl(result.midi), 'score.midi')}
                    style={{
                        padding: '1rem', background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer',
                        border: '1px solid var(--border)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%', fontFamily: 'inherit'
                    }}>
                    <FileAudio size={20} />
                    {lang === 'pt' ? 'Baixar MIDI' : 'Download MIDI'}
                </button>
                <button
                    onClick={() => handleDownload(getResultUrl(result.log), 'log.txt')}
                    style={{
                        padding: '1rem', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer',
                        border: '1px dashed var(--border)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%', fontFamily: 'inherit'
                    }}>
                    <FileText size={20} />
                    {lang === 'pt' ? 'Baixar log' : 'Download log'}
                </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: '2rem', marginTop: '1rem' }}>
                <button onClick={onReset} style={{ background: 'transparent', color: 'var(--accent)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <RefreshCw size={18} /> {lang === 'pt' ? 'Converter outro áudio' : 'Convert another audio'}
                </button>
            </div>
        </div>
    );
};
