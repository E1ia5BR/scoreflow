// Use relative URLs so the Vite proxy (dev) or same-origin (prod) handles routing.
// This allows the app to work both locally and through ngrok/deployed URLs.
export const BASE_URL = '';
const API_URL = `/api`;
const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api`;

export const getResultUrl = (path: string) => {
    if (path === 'dummy_url') return path;
    return `${path}`;
};

export const uploadAudio = async (file: File, timeSignature: string = 'auto', audioType: string = 'piano') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('time_signature', timeSignature);
    formData.append('audio_type', audioType);

    const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
    }

    return response.json(); // { job_id, status }
};

export const getJobStatus = async (jobId: string) => {
    const response = await fetch(`${API_URL}/jobs/${jobId}/status`);
    if (!response.ok) throw new Error('Failed to fetch status');
    return response.json();
};

export const getJobResult = async (jobId: string) => {
    const response = await fetch(`${API_URL}/jobs/${jobId}/result`);
    if (!response.ok) throw new Error('Failed to fetch result');
    return response.json();
};

export const getHistory = async () => {
    const response = await fetch(`${API_URL}/history`);
    if (!response.ok) throw new Error('Failed to fetch history');
    return response.json();
};

export const deleteJob = async (jobId: string) => {
    const response = await fetch(`${API_URL}/jobs/${jobId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Failed to delete job');
    return response.json();
};

/**
 * Subscribe to real-time job status updates via WebSocket.
 * Falls back to polling if WebSocket connection fails.
 *
 * @param jobId - The job ID to subscribe to.
 * @param onUpdate - Callback with status data (same format as getJobStatus).
 * @returns A cleanup function to close the connection.
 */
export const subscribeJobStatus = (
    jobId: string,
    onUpdate: (data: { id: string; status: string; progress: number; message: string }) => void
): (() => void) => {
    let ws: WebSocket | null = null;
    let fallbackInterval: ReturnType<typeof setInterval> | null = null;
    let closed = false;

    const startPollingFallback = () => {
        if (closed || fallbackInterval) return;
        console.log('[api] WebSocket unavailable, falling back to polling');
        fallbackInterval = setInterval(async () => {
            if (closed) {
                if (fallbackInterval) clearInterval(fallbackInterval);
                return;
            }
            try {
                const data = await getJobStatus(jobId);
                onUpdate(data);
                if (data.status === 'ready' || data.status === 'error') {
                    if (fallbackInterval) clearInterval(fallbackInterval);
                }
            } catch (err) {
                console.error('Polling error', err);
            }
        }, 2000);
    };

    try {
        ws = new WebSocket(`${WS_URL}/ws/${jobId}`);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.error) {
                    // Server reported an error (e.g., Redis unavailable)
                    ws?.close();
                    startPollingFallback();
                    return;
                }
                onUpdate(data);
            } catch (e) {
                console.error('[api] Failed to parse WS message:', e);
            }
        };

        ws.onerror = () => {
            startPollingFallback();
        };

        ws.onclose = () => {
            // If not intentionally closed, fall back to polling
            if (!closed) {
                startPollingFallback();
            }
        };
    } catch (e) {
        startPollingFallback();
    }

    // Return cleanup function
    return () => {
        closed = true;
        if (ws && ws.readyState <= WebSocket.OPEN) {
            ws.close();
        }
        if (fallbackInterval) {
            clearInterval(fallbackInterval);
        }
    };
};
