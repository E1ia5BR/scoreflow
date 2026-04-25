import React from 'react';
import { Upload, Activity, Headphones, FileMusic, CheckCircle, XCircle } from 'lucide-react';

interface ProgressProps {
    status: string;
    progress: number;
    message: string;
    lang: 'pt' | 'en';
}

const steps = [
    { id: 'uploading', icon: Upload, pt: 'Enviando', en: 'Uploading' },
    { id: 'analyzing', icon: Activity, pt: 'Analisando', en: 'Analyzing' },
    { id: 'transcribing', icon: Headphones, pt: 'Transcrevendo', en: 'Transcribing' },
    { id: 'converting', icon: FileMusic, pt: 'Convertendo', en: 'Converting' },
];

export const ProgressBar = ({ status, progress, message, lang }: ProgressProps) => {
    const currentIndex = steps.findIndex(s => s.id === status);
    const isError = status === 'error';
    const isReady = status === 'ready';

    return (
        <div style={{ background: 'var(--card-bg)', padding: '2.5rem 2rem', borderRadius: '12px', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2rem', position: 'relative' }}>
                {/* Progress Line */}
                <div style={{
                    position: 'absolute', top: '24px', left: '10%', right: '10%', height: '4px', background: 'var(--border)', zIndex: 0
                }}>
                    <div style={{
                        height: '100%',
                        background: isError ? 'var(--error)' : 'var(--accent)',
                        width: `${isReady ? 100 : Math.max(0, (currentIndex / (steps.length - 1)) * 100)}%`,
                        transition: 'width 0.5s ease'
                    }} />
                </div>

                {steps.map((step, idx) => {
                    const isActive = status === step.id;
                    const isPassed = isReady || currentIndex > idx;
                    const Icon = step.icon;

                    let color = 'var(--text-secondary)';
                    let bg = 'var(--bg-primary)';
                    let borderColor = 'var(--border)';

                    if (isActive) {
                        color = 'var(--accent)';
                        borderColor = 'var(--accent)';
                    } else if (isPassed) {
                        color = 'var(--bg-primary)';
                        bg = 'var(--success)';
                        borderColor = 'var(--success)';
                    }

                    if (isError && isActive) {
                        color = 'var(--error)';
                        borderColor = 'var(--error)';
                    }

                    return (
                        <div key={step.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 1, gap: '0.5rem', width: '80px' }}>
                            <div style={{
                                width: '48px', height: '48px', borderRadius: '50%',
                                background: bg, border: `2px solid ${borderColor}`,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                color: color,
                                transition: 'all 0.3s ease',
                                transform: isActive ? 'scale(1.1)' : 'scale(1)'
                            }}>
                                {isPassed && !isError ? <CheckCircle size={24} color={color} /> :
                                    (isError && isActive ? <XCircle size={24} color={color} /> : <Icon size={24} />)}
                            </div>
                            <span style={{
                                fontSize: '0.85rem',
                                fontWeight: isActive ? 600 : 400,
                                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                                textAlign: 'center'
                            }}>
                                {lang === 'pt' ? step.pt : step.en}
                            </span>
                        </div>
                    );
                })}
            </div>

            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
                <h4 style={{ color: isError ? 'var(--error)' : 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    {isError ? (lang === 'pt' ? 'Erro no Processamento' : 'Processing Error') : `${Math.round(progress)}%`}
                </h4>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
                    {message}
                </p>
            </div>
        </div>
    );
};
