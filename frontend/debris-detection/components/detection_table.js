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
