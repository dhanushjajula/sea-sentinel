import os
from pathlib import Path

def write_file(path_str, content):
    p = Path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Wrote {path_str}")

# 1. Frontend Shared API Client
write_file("frontend/shared/js/api_client.js", """
/**
 * Sea Sentinel Unified REST API Client
 */
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:8000' 
    : window.location.origin;

class SeaSentinelAPI {
    static async healthCheck() {
        try {
            const resp = await fetch(`${API_BASE_URL}/health`);
            return await resp.json();
        } catch (err) {
            console.warn('[API Client] Health check offline:', err);
            return { status: 'offline', error: err.message };
        }
    }

    static async analyzeSonarImage(formData) {
        const resp = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            body: formData
        });
        if (!resp.ok) throw new Error(`Analysis failed with status ${resp.status}`);
        return await resp.json();
    }

    static async getRecentAudits(limit = 20) {
        const resp = await fetch(`${API_BASE_URL}/audit/recent?limit=${limit}`);
        if (!resp.ok) return [];
        return await resp.json();
    }

    static async getAblationMetrics() {
        const resp = await fetch(`${API_BASE_URL}/ablation/metrics`);
        if (!resp.ok) return null;
        return await resp.json();
    }
}

window.SeaSentinelAPI = SeaSentinelAPI;
""")

# 2. Frontend Geolocation Component
write_file("frontend/geolocation/components/gis_map.js", """
/**
 * Sea Sentinel GIS Interactive Map Component
 */
class SonarGISMap {
    constructor(containerId = 'map') {
        this.containerId = containerId;
        this.map = null;
        this.markersLayer = null;
    }

    init(defaultLat = 13.0827, defaultLon = 80.2707, zoom = 12) {
        if (!document.getElementById(this.containerId)) return;
        if (typeof L === 'undefined') {
            console.warn('[GIS Map] Leaflet library not loaded.');
            return;
        }

        this.map = L.map(this.containerId).setView([defaultLat, defaultLon], zoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors | Sea Sentinel NIOT'
        }).addTo(this.map);

        this.markersLayer = L.layerGroup().addTo(this.map);
    }

    plotTargets(targets = []) {
        if (!this.markersLayer) return;
        this.markersLayer.clearLayers();

        targets.forEach(t => {
            if (t.latitude && t.longitude) {
                const marker = L.circleMarker([t.latitude, t.longitude], {
                    radius: 7,
                    fillColor: t.risk_level === 'CRITICAL' ? '#ff3232' : '#00e5ff',
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85
                });
                marker.bindPopup(`<b>${t.class_name.toUpperCase()}</b><br>Conf: ${(t.confidence*100).toFixed(1)}%<br>Risk: ${t.risk_level || 'N/A'}`);
                this.markersLayer.addLayer(marker);
            }
        });
    }
}

window.SonarGISMap = SonarGISMap;
""")

# 3. Frontend Visualization Component (Waterfall Viewer)
write_file("frontend/visualization/components/waterfall_viewer.js", """
/**
 * Dual Waterfall Sonar Viewer Component
 */
class DualWaterfallViewer {
    constructor(rawCanvasId = 'rawCanvas', procCanvasId = 'processedCanvas') {
        this.rawCanvas = document.getElementById(rawCanvasId);
        this.procCanvas = document.getElementById(procCanvasId);
    }

    render(rawSrc, procSrc, detections = []) {
        if (this.rawCanvas && rawSrc) {
            const ctx = this.rawCanvas.getContext('2d');
            const img = new Image();
            img.onload = () => {
                this.rawCanvas.width = img.width;
                this.rawCanvas.height = img.height;
                ctx.drawImage(img, 0, 0);
            };
            img.src = rawSrc;
        }

        if (this.procCanvas && procSrc) {
            const ctx = this.procCanvas.getContext('2d');
            const img = new Image();
            img.onload = () => {
                this.procCanvas.width = img.width;
                this.procCanvas.height = img.height;
                ctx.drawImage(img, 0, 0);
                
                // Render bounding boxes
                detections.forEach(det => {
                    if (det.bbox) {
                        const [x1, y1, x2, y2] = det.bbox;
                        ctx.strokeStyle = '#00e5ff';
                        ctx.lineWidth = 2;
                        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                    }
                });
            };
            img.src = procSrc;
        }
    }
}

window.DualWaterfallViewer = DualWaterfallViewer;
""")

# 4. Frontend Debris Detection Component
write_file("frontend/debris-detection/components/detection_table.js", """
/**
 * Marine Debris Detection Table Renderer
 */
class DebrisDetectionTable {
    constructor(tableContainerId = 'detectionsTableBody') {
        this.container = document.getElementById(tableContainerId);
    }

    render(targets = []) {
        if (!this.container) return;
        this.container.innerHTML = '';

        if (targets.length === 0) {
            this.container.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No acoustic targets detected</td></tr>';
            return;
        }

        targets.forEach((t, idx) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>#${idx + 1}</strong></td>
                <td><span class="badge badge-debris">${t.class_name}</span></td>
                <td>${(t.confidence * 100).toFixed(1)}%</td>
                <td>${t.area_px || '—'} px</td>
                <td>${t.latitude ? t.latitude.toFixed(5) : '—'}, ${t.longitude ? t.longitude.toFixed(5) : '—'}</td>
                <td><span class="badge ${t.risk_level === 'CRITICAL' ? 'badge-critical' : 'badge-normal'}">${t.risk_level || 'NORMAL'}</span></td>
                <td><button class="btn btn-sm btn-outline-cyan" onclick="window.focusTarget(${idx})">Inspect</button></td>
            `;
            this.container.appendChild(tr);
        });
    }
}

window.DebrisDetectionTable = DebrisDetectionTable;
""")

# 5. Frontend Dashboard Page Controller
write_file("frontend/dashboard/pages/dashboard_page.js", """
/**
 * Main Sea Sentinel Dashboard Controller
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Sea Sentinel v2.0 Modular Dashboard initialized.');
    
    // Initialize Subcomponents
    if (window.SonarGISMap) {
        window.gisMap = new SonarGISMap('map');
        window.gisMap.init();
    }
    if (window.DualWaterfallViewer) {
        window.waterfallViewer = new DualWaterfallViewer('rawCanvas', 'processedCanvas');
    }
    if (window.DebrisDetectionTable) {
        window.debrisTable = new DebrisDetectionTable('detectionsTableBody');
    }

    // Connect Health Check
    if (window.SeaSentinelAPI) {
        SeaSentinelAPI.healthCheck().then(h => {
            const el = document.getElementById('backendStatusBadge');
            if (el) {
                el.innerText = h.status === 'healthy' || h.status === 'ok' ? 'ONLINE (FASTAPI 2.0)' : 'OFFLINE';
                el.className = h.status === 'healthy' || h.status === 'ok' ? 'badge badge-success' : 'badge badge-danger';
            }
        });
    }
});
""")

print("✓ Frontend modular components and pages created.")
