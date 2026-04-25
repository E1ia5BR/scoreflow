import { Clock, CheckCircle, XCircle, ChevronRight, Trash2 } from 'lucide-react';

interface HistoryItem {
    id: string;
    name: string;
    date: string;
    status: string;
    duration?: string;
}

export const HistoryList = ({ items, onSelect, onDelete, lang }: { items: HistoryItem[], onSelect: (id: string) => void, onDelete: (id: string) => void, lang: 'pt' | 'en' }) => {
    if (items.length === 0) {
        return (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)', border: '1px dashed var(--border)', borderRadius: '12px' }}>
                {lang === 'pt' ? 'Nenhuma conversão realizada ainda.' : 'No conversions yet.'}
            </div>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                {lang === 'pt' ? 'Histórico' : 'History'}
            </h3>
            {items.slice(0, 10).map((item) => (
                <div key={item.id} style={{
                    display: 'flex', alignItems: 'center', gap: '1rem',
                    padding: '1rem', background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '10px',
                    transition: 'transform 0.2s ease',
                    cursor: 'pointer'
                }} onClick={() => onSelect(item.id)}>
                    <div style={{ color: item.status === 'ready' ? 'var(--success)' : (item.status === 'error' ? 'var(--error)' : 'var(--accent)') }}>
                        {item.status === 'ready' ? <CheckCircle size={20} /> : (item.status === 'error' ? <XCircle size={20} /> : <Clock size={20} />)}
                    </div>

                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 500, fontSize: '0.95rem' }}>{item.name}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{item.date} • {item.duration || '--:--'}</div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button onClick={(e) => { e.stopPropagation(); onDelete(item.id); }} style={{ padding: '0.4rem', color: 'var(--text-secondary)', background: 'transparent' }}>
                            <Trash2 size={16} />
                        </button>
                        <ChevronRight size={20} color="var(--border)" />
                    </div>
                </div>
            ))}
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center', marginTop: '0.5rem' }}>
                {lang === 'pt' ? 'Arquivos são mantidos por 7 dias.' : 'Files are kept for 7 days.'}
            </p>
        </div>
    );
};
