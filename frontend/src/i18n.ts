/**
 * i18n.ts — Centralized internationalization system.
 *
 * Replaces inline `lang === 'pt' ? 'X' : 'Y'` patterns with a clean
 * dictionary-based approach. Easy to add new languages (es, fr, etc).
 */

export type Lang = 'pt' | 'en';

const translations: Record<Lang, Record<string, string>> = {
    pt: {
        // Header
        'app.title.prefix': 'Score',
        'app.title.suffix': 'Flow',

        // Upload Zone
        'upload.what': 'O que você está enviando?',
        'upload.piano': '🎹 Piano ou Banda (Múltiplas Notas)',
        'upload.vocal': '🎙️ Voz ou Solo (Melodia Simples)',
        'upload.timeSig': 'Fórmula de Compasso da Música:',
        'upload.auto': '🔍 Detectar Automaticamente',
        'upload.dropTitle': 'Arraste seu áudio aqui',
        'upload.dropSubtitle': 'ou clique para selecionar um arquivo',
        'upload.selectFile': 'Selecionar arquivo',
        'upload.maxSize': 'Máx. 200 MB • MP3 ou WAV',
        'upload.lgpd': 'Ao enviar, você concorda que os dados serão excluídos em 7 dias (LGPD).',
        'upload.oneFile': 'Envie apenas um arquivo por vez.',
        'upload.unsupported': 'Formato não suportado. Envie MP3 ou WAV.',
        'upload.tooLarge': 'Arquivo excede limite de 200MB.',
        'upload.changeFile': 'Trocar arquivo',
        'upload.process': '🚀 Processar Partitura',
        'upload.remove': 'Remover',

        // Progress
        'progress.uploading': 'Enviando...',
        'progress.analyzing': 'Analisando...',
        'progress.transcribing': 'Transcrevendo...',
        'progress.converting': 'Convertendo...',

        // Result
        'result.ready': 'Sua partitura está pronta!',
        'result.subtitle': 'Visualize, baixe ou ajuste o resultado.',
        'result.downloadXml': 'Baixar MusicXML',
        'result.downloadPdf': 'Baixar PDF',
        'result.downloadMidi': 'Baixar MIDI',
        'result.downloadLog': 'Baixar log',
        'result.convertAnother': 'Converter outro áudio',

        // History
        'history.title': 'Histórico',
        'history.empty': 'Nenhuma conversão realizada ainda.',
        'history.retention': 'Arquivos são mantidos por 7 dias.',
        'history.loadFailed': 'Falha ao carregar do histórico.',

        // Errors
        'error.render': 'Erro de renderização. Tente recarregar.',
        'error.retry': 'Recarregar',
        'error.upload': 'Falha no upload',
    },

    en: {
        // Header
        'app.title.prefix': 'Score',
        'app.title.suffix': 'Flow',

        // Upload Zone
        'upload.what': 'What are you uploading?',
        'upload.piano': '🎹 Piano or Band (Polyphonic)',
        'upload.vocal': '🎙️ Vocals or Solo (Monophonic)',
        'upload.timeSig': 'Song Time Signature:',
        'upload.auto': '🔍 Auto-detect',
        'upload.dropTitle': 'Drop your audio here',
        'upload.dropSubtitle': 'or click to select a file',
        'upload.selectFile': 'Select file',
        'upload.maxSize': 'Max 200 MB • MP3 or WAV',
        'upload.lgpd': 'By uploading, you agree data is deleted in 7 days.',
        'upload.oneFile': 'Please upload one file at a time.',
        'upload.unsupported': 'Unsupported format. Please upload MP3 or WAV.',
        'upload.tooLarge': 'File exceeds 200MB limit.',
        'upload.changeFile': 'Change file',
        'upload.process': '🚀 Process Score',
        'upload.remove': 'Remove',

        // Progress
        'progress.uploading': 'Uploading...',
        'progress.analyzing': 'Analyzing...',
        'progress.transcribing': 'Transcribing...',
        'progress.converting': 'Converting...',

        // Result
        'result.ready': 'Your score is ready!',
        'result.subtitle': 'Preview, download, or adjust the result.',
        'result.downloadXml': 'Download MusicXML',
        'result.downloadPdf': 'Download PDF',
        'result.downloadMidi': 'Download MIDI',
        'result.downloadLog': 'Download log',
        'result.convertAnother': 'Convert another audio',

        // History
        'history.title': 'History',
        'history.empty': 'No conversions yet.',
        'history.retention': 'Files are kept for 7 days.',
        'history.loadFailed': 'Failed to load from history.',

        // Errors
        'error.render': 'Render error. Try reloading.',
        'error.retry': 'Reload',
        'error.upload': 'Upload failed',
    },
};

/**
 * Create a translation function for the given language.
 *
 * Usage:
 *   const t = useT('pt');
 *   t('upload.dropTitle') → 'Arraste seu áudio aqui'
 */
export function useT(lang: Lang): (key: string) => string {
    const dict = translations[lang] || translations.en;
    return (key: string) => dict[key] || key;
}
