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
