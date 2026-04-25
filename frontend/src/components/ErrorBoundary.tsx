import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
    children?: ReactNode;
    lang: 'pt' | 'en';
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Uncaught error:', error, errorInfo);
    }

    public render() {
        if (this.state.hasError) {
            const { lang } = this.props;
            return (
                <div style={{ padding: '2rem', textAlign: 'center', background: 'var(--card-bg)', border: '1px solid var(--error)', borderRadius: '12px', color: 'var(--error)' }}>
                    <AlertTriangle size={48} style={{ margin: '0 auto 1rem' }} />
                    <h2 style={{ fontSize: '1.25rem', marginBottom: '0.5rem' }}>
                        {lang === 'pt' ? 'Erro de Renderização' : 'Rendering Error'}
                    </h2>
                    <p style={{ color: 'var(--text-secondary)' }}>
                        {lang === 'pt' ? 'Ocorreu um erro ao exibir a partitura. O arquivo pode ser muito complexo ou ter formato não suportado visualmente.' : 'An error occurred displaying the score. The file might be too complex or in an unsupported visual format.'}
                    </p>
                </div>
            );
        }

        return this.props.children;
    }
}
