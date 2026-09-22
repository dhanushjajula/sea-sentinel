/**
 * Sea Sentinel Unified REST API Client
 */
<<<<<<< HEAD
const API_CLIENT_BASE_URL = (typeof API_BASE_URL !== 'undefined') 
    ? API_BASE_URL 
    : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? 'http://localhost:8000' 
        : window.location.origin);
=======
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:8000' 
    : window.location.origin;
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f

class SeaSentinelAPI {
    static async healthCheck() {
        try {
<<<<<<< HEAD
            const resp = await fetch(`${API_CLIENT_BASE_URL}/health`);
=======
            const resp = await fetch(`${API_BASE_URL}/health`);
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f
            return await resp.json();
        } catch (err) {
            console.warn('[API Client] Health check offline:', err);
            return { status: 'offline', error: err.message };
        }
    }

    static async analyzeSonarImage(formData) {
<<<<<<< HEAD
        const resp = await fetch(`${API_CLIENT_BASE_URL}/analyze`, {
=======
        const resp = await fetch(`${API_BASE_URL}/analyze`, {
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f
            method: 'POST',
            body: formData
        });
        if (!resp.ok) throw new Error(`Analysis failed with status ${resp.status}`);
        return await resp.json();
    }

    static async getRecentAudits(limit = 20) {
<<<<<<< HEAD
        const resp = await fetch(`${API_CLIENT_BASE_URL}/audit/recent?limit=${limit}`);
=======
        const resp = await fetch(`${API_BASE_URL}/audit/recent?limit=${limit}`);
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f
        if (!resp.ok) return [];
        return await resp.json();
    }

    static async getAblationMetrics() {
<<<<<<< HEAD
        const resp = await fetch(`${API_CLIENT_BASE_URL}/ablation/metrics`);
=======
        const resp = await fetch(`${API_BASE_URL}/ablation/metrics`);
>>>>>>> 449ab6fff1827af49bd4a885932dc0cd8729161f
        if (!resp.ok) return null;
        return await resp.json();
    }
}

window.SeaSentinelAPI = SeaSentinelAPI;
