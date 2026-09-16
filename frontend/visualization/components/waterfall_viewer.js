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
