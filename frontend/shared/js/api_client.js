/**
 * Sea Sentinel Unified REST API Client
 */
const API_CLIENT_BASE_URL = (typeof API_BASE_URL !== 'undefined') 
    ? API_BASE_URL 
    : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? 'http://localhost:8000' 
        : window.location.origin);

class SeaSentinelAPI {
    static async healthCheck() {
        try {
            const resp = await fetch(`${API_CLIENT_BASE_URL}/health`);
            return await resp.json();
        } catch (err) {
            console.warn('[API Client] Health check offline:', err);
            return { status: 'offline', error: err.message };
        }
    }

    static async analyzeSonarImage(formData) {
        const resp = await fetch(`${API_CLIENT_BASE_URL}/analyze`, {
            method: 'POST',
            body: formData
        });
        if (!resp.ok) throw new Error(`Analysis failed with status ${resp.status}`);
        return await resp.json();
    }

    static async getRecentAudits(limit = 20) {
        const resp = await fetch(`${API_CLIENT_BASE_URL}/audit/recent?limit=${limit}`);
        if (!resp.ok) return [];
        return await resp.json();
    }

    static async getAblationMetrics() {
        const resp = await fetch(`${API_CLIENT_BASE_URL}/ablation/metrics`);
        if (!resp.ok) return null;
        return await resp.json();
    }
}

window.SeaSentinelAPI = SeaSentinelAPI;
