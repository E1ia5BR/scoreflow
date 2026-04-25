/**
 * Frontend tests for i18n, API service, and component logic.
 *
 * Run: npm test
 */

import { describe, it, expect } from 'vitest';
import { useT } from '../i18n';
import type { Lang } from '../i18n';

// ---------------------------------------------------------------------------
// Tests: i18n
// ---------------------------------------------------------------------------

describe('i18n', () => {
    it('returns Portuguese translations', () => {
        const t = useT('pt');
        expect(t('upload.dropTitle')).toBe('Arraste seu áudio aqui');
        expect(t('result.ready')).toBe('Sua partitura está pronta!');
    });

    it('returns English translations', () => {
        const t = useT('en');
        expect(t('upload.dropTitle')).toBe('Drop your audio here');
        expect(t('result.ready')).toBe('Your score is ready!');
    });

    it('returns key when translation missing', () => {
        const t = useT('pt');
        expect(t('nonexistent.key')).toBe('nonexistent.key');
    });

    it('all PT keys have EN equivalents', () => {
        const tPt = useT('pt');
        const tEn = useT('en');

        // Test a representative set of keys
        const keys = [
            'upload.what', 'upload.piano', 'upload.vocal',
            'upload.timeSig', 'upload.auto', 'upload.dropTitle',
            'result.ready', 'result.downloadXml', 'result.downloadMidi',
            'history.title', 'history.empty',
        ];

        for (const key of keys) {
            const ptVal = tPt(key);
            const enVal = tEn(key);
            expect(ptVal).not.toBe(key); // PT should have a translation
            expect(enVal).not.toBe(key); // EN should have a translation
            expect(ptVal).not.toBe(enVal); // They should be different
        }
    });
});

// ---------------------------------------------------------------------------
// Tests: API service URL construction
// ---------------------------------------------------------------------------

describe('API URL construction', () => {
    it('BASE_URL is localhost:8000', async () => {
        const { BASE_URL } = await import('../services/api');
        expect(BASE_URL).toBe('http://localhost:8000');
    });

    it('getResultUrl prepends BASE_URL', async () => {
        const { getResultUrl } = await import('../services/api');
        const url = getResultUrl('/storage/results/abc/output.musicxml');
        expect(url).toContain('http://localhost:8000');
        expect(url).toContain('/storage/results/abc/output.musicxml');
    });

    it('getResultUrl handles dummy_url', async () => {
        const { getResultUrl } = await import('../services/api');
        expect(getResultUrl('dummy_url')).toBe('dummy_url');
    });
});
