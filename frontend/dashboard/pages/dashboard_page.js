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
