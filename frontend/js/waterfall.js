/**
 * Sea Sentinel: Interactive Sonar Waterfall Viewer
 * Renders acoustic waterfall scans with Port/Starboard channels, nadir line, and target bounding overlays.
 * Supports multi-mode inspection, independent layer toggles (YOLO, U-Net, Fusion, Verification, IDs),
 * and interactive Zoom In / Zoom Out / Pan / Reset Zoom controls.
 */

class WaterfallViewer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.targets = [];
    this.selectedTargetId = null;
    this.currentMode = "overlay"; // "raw" | "enhanced" | "overlay"

    // Zoom & Pan state
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.minScale = 0.5;
    this.maxScale = 5.0;
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.dragStartPanX = 0;
    this.dragStartPanY = 0;
    this.hasMoved = false;

    // Independent layer visibility toggles
    this.layers = {
      yolo: true,
      unet: true,
      fusion: true,
      verify: true,
      ids: true
    };

    // Dynamic confidence and sensitivity thresholds
    this.yoloConfThreshold = 0.45;
    this.unetSensThreshold = 0.50;

    this.rawImage = null;
    this.enhancedImage = null;
    this.annotatedImage = null;

    // Default acoustic waterfall canvas size
    this.canvas.width = 1200;
    this.canvas.height = 420;
    this._generateSyntheticWaterfall();
    this._initEvents();
  }

  zoomIn(factor = 1.25) {
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;
    this.zoomAt(cx, cy, factor);
  }

  zoomOut(factor = 0.8) {
    const cx = this.canvas.width / 2;
    const cy = this.canvas.height / 2;
    this.zoomAt(cx, cy, factor);
  }

  resetZoom() {
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this._updateZoomBadge();
    this.render();
  }

  resize() {
    if (!this.canvas) return;
    const parent = this.canvas.parentElement;
    if (parent) {
      const rect = parent.getBoundingClientRect();
      if (rect.width > 0) {
        if (this.rawImage && this.rawImage.naturalWidth > 0) {
          const aspect = this.rawImage.naturalHeight / this.rawImage.naturalWidth;
          this.canvas.width = Math.min(1600, Math.max(800, Math.round(rect.width)));
          this.canvas.height = Math.round(this.canvas.width * aspect);
        } else {
          this.canvas.width = Math.max(800, Math.round(rect.width));
          this.canvas.height = Math.max(420, Math.round(rect.height || 420));
        }
      }
    }
    this.render();
  }

  zoomAt(canvasX, canvasY, factor) {
    const newScale = Math.min(this.maxScale, Math.max(this.minScale, this.scale * factor));
    if (Math.abs(newScale - this.scale) < 0.001) return;

    // Keep the point under the cursor at the same canvas position
    this.panX = canvasX - (canvasX - this.panX) * (newScale / this.scale);
    this.panY = canvasY - (canvasY - this.panY) * (newScale / this.scale);
    this.scale = newScale;

    this._clampPan();
    this._updateZoomBadge();
    this.render();
  }

  _clampPan() {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const maxPanX = w * (this.scale - 0.2);
    const minPanX = -w * (this.scale - 0.2);
    const maxPanY = h * (this.scale - 0.2);
    const minPanY = -h * (this.scale - 0.2);

    this.panX = Math.min(maxPanX, Math.max(minPanX, this.panX));
    this.panY = Math.min(maxPanY, Math.max(minPanY, this.panY));
  }

  _updateZoomBadge() {
    const pct = Math.round(this.scale * 100);
    const badge = document.getElementById("waterfallZoomLevel");
    if (badge) {
      badge.textContent = `${pct}%`;
    }
  }

  setTargets(targets) {
    this.targets = targets || [];
    if (Array.isArray(this.targets)) {
      this.targets.forEach(t => {
        if (typeof window.registerGisDebrisTarget === 'function') {
          window.registerGisDebrisTarget(t);
        }
      });
    }
    this.render();
  }

  _generateSyntheticWaterfall() {
    const w = this.canvas.width;
    const h = this.canvas.height;
    const imgData = this.ctx.createImageData(w, h);
    const data = imgData.data;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const idx = (y * w + x) * 4;
        const distFromNadir = Math.abs(x - w / 2);

        // Nadir blind zone (dark acoustic void near center trackline)
        if (distFromNadir < 18) {
          const nadirDark = Math.floor(Math.random() * 18);
          data[idx] = nadirDark;
          data[idx + 1] = nadirDark + 5;
          data[idx + 2] = nadirDark + 10;
          data[idx + 3] = 255;
          continue;
        }

        // Ambient seafloor backscatter with grazing angle falloff
        let val = 75 + Math.sin(y * 0.08 + x * 0.02) * 15 + (Math.random() * 30 - 15);
        val = Math.max(25, Math.min(180, val));

        data[idx] = Math.floor(val * 0.85);       // Deep bronze / copper sonar tone
        data[idx + 1] = Math.floor(val * 0.95);
        data[idx + 2] = Math.floor(val * 1.15);
        data[idx + 3] = 255;
      }
    }
    this.ctx.putImageData(imgData, 0, 0);
  }

  selectTarget(targetId) {
    this.selectedTargetId = targetId;
    this.render();
  }

  highlightTarget(targetId) {
    this.selectTarget(targetId);
  }

  setViewMode(mode) {
    this.currentMode = mode;
    this.render();
  }

  setLayerVisibility(layerName, isVisible) {
    if (this.layers.hasOwnProperty(layerName)) {
      this.layers[layerName] = Boolean(isVisible);
      this.render();
    }
  }

  setThresholds({ yoloConf, unetSens } = {}) {
    if (yoloConf !== undefined) this.yoloConfThreshold = Number(yoloConf);
    if (unetSens !== undefined) this.unetSensThreshold = Number(unetSens);
    this.render();
  }

  _isTargetActive(t) {
    const srcCat = t.source_category || (t.sources && t.sources.length > 1 ? "BOTH" : (t.sources && t.sources[0] === "unet" ? "UNET_ONLY" : "YOLO_ONLY"));
    const hasYolo = t.sources ? t.sources.includes("yolo") : (srcCat !== "UNET_ONLY");
    const hasUnet = t.sources ? t.sources.includes("unet") : (srcCat !== "YOLO_ONLY");
    const conf = Number(t.confidence || t.calibrated_confidence || 0.85);

    const yoloMin = this.yoloConfThreshold !== undefined ? this.yoloConfThreshold : 0.45;
    const unetMin = this.unetSensThreshold !== undefined ? Math.max(0.20, 1.0 - this.unetSensThreshold * 0.7) : 0.45;

    const passesYolo = hasYolo && (conf >= yoloMin);
    const passesUnet = hasUnet && (conf >= unetMin);

    return passesYolo || passesUnet;
  }

  _isImageValid(img) {
    return Boolean(img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0);
  }

  _loadImage(url, callback) {
    if (!url) {
      callback(null);
      return;
    }
    const img = new Image();
    img.onload = () => {
      callback(img);
    };
    img.onerror = () => {
      const fallbackImg = new Image();
      fallbackImg.onload = () => callback(fallbackImg);
      fallbackImg.onerror = () => {
        console.warn("Could not decode sonar scan image at URL:", url);
        callback(null);
      };
      fallbackImg.src = url;
    };
    img.src = url;
  }

  loadSonarImages({ rawUrl, enhancedUrl, annotatedUrl }) {
    this._loadImage(rawUrl, (img) => {
      this.rawImage = img;
      if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
        this.canvas.width = Math.min(1600, Math.max(800, img.naturalWidth));
        this.canvas.height = Math.round(this.canvas.width * (img.naturalHeight / img.naturalWidth));
      }
      this.render();
    });

    this._loadImage(enhancedUrl, (img) => {
      this.enhancedImage = img;
      this.render();
    });

    this._loadImage(annotatedUrl, (img) => {
      this.annotatedImage = img;
      this.render();
    });
  }

  clearImages() {
    this.rawImage = null;
    this.enhancedImage = null;
    this.annotatedImage = null;
    this.targets = [];
    this.selectedTargetId = null;
  }

  showRejectionPlaceholder(reason) {
    this.clearImages();
    const w = this.canvas.width;
    const h = this.canvas.height;
    const ctx = this.ctx;

    ctx.fillStyle = "#030a16";
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = "rgba(255, 51, 102, 0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "rgba(255, 51, 102, 0.35)";
    ctx.beginPath();
    ctx.moveTo(w / 2, 0);
    ctx.lineTo(w / 2, h);
    ctx.stroke();
    ctx.setLineDash([]);

    const boxW = Math.min(680, w - 40);
    const boxH = 140;
    const boxX = (w - boxW) / 2;
    const boxY = (h - boxH) / 2;

    ctx.fillStyle = "rgba(18, 5, 12, 0.92)";
    ctx.strokeStyle = "rgba(255, 51, 102, 0.55)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(boxX, boxY, boxW, boxH, 8);
    } else {
      ctx.rect(boxX, boxY, boxW, boxH);
    }
    ctx.fill();
    ctx.stroke();

    ctx.font = "bold 15px 'JetBrains Mono', monospace";
    ctx.fillStyle = "#ff3366";
    ctx.textAlign = "center";
    ctx.fillText("⚠ ACOUSTIC SENSOR REJECTION: NON-SONAR INPUT", w / 2, boxY + 38);

    ctx.font = "12px 'Outfit', sans-serif";
    ctx.fillStyle = "#fca5a5";
    const cleanReason = reason ? (reason.length > 90 ? reason.substring(0, 90) + "..." : reason) : "Optical or non-acoustic raster detected.";
    ctx.fillText(cleanReason, w / 2, boxY + 68);

    ctx.font = "11px 'JetBrains Mono', monospace";
    ctx.fillStyle = "#8da2be";
    ctx.fillText("Sea Sentinel operates strictly on Side-Scan Sonar (SSS) acoustic backscatter.", w / 2, boxY + 95);
    ctx.fillText("No acoustic targets, shadow reliefs, or geolocations plotted.", w / 2, boxY + 115);
  }

  _getTargetCanvasCoords(t, w, h) {
    const norm = t.norm_bbox;
    if (norm && (norm.x2 > norm.x1)) {
      const x1 = Math.max(0, norm.x1 * w);
      const y1 = Math.max(0, norm.y1 * h);
      const x2 = Math.min(w, norm.x2 * w);
      const y2 = Math.min(h, norm.y2 * h);
      return { x1, y1, x2, y2, bw: Math.max(12, x2 - x1), bh: Math.max(12, y2 - y1) };
    }

    if (t.norm_polygon && Array.isArray(t.norm_polygon) && t.norm_polygon.length >= 3) {
      let minX = 1.0, minY = 1.0, maxX = 0.0, maxY = 0.0;
      t.norm_polygon.forEach(pt => {
        if (pt[0] < minX) minX = pt[0];
        if (pt[1] < minY) minY = pt[1];
        if (pt[0] > maxX) maxX = pt[0];
        if (pt[1] > maxY) maxY = pt[1];
      });
      if (maxX > minX && maxY > minY) {
        const padX = 8 / w;
        const padY = 8 / h;
        const x1 = Math.max(0, (minX - padX) * w);
        const y1 = Math.max(0, (minY - padY) * h);
        const x2 = Math.min(w, (maxX + padX) * w);
        const y2 = Math.min(h, (maxY + padY) * h);
        return { x1, y1, x2, y2, bw: Math.max(12, x2 - x1), bh: Math.max(12, y2 - y1) };
      }
    }
    let b = t.pixel_bbox || t.bbox || {};
    let bx1 = 0, by1 = 0, bx2 = 80, by2 = 60;
    if (Array.isArray(b)) {
      if (b.length >= 4) {
        bx1 = b[0];
        by1 = b[1];
        bx2 = b[0] + b[2];
        by2 = b[1] + b[3];
      }
    } else if (typeof b === 'object' && b !== null) {
      bx1 = b.x1 != null ? b.x1 : (b.x != null ? b.x : 0);
      by1 = b.y1 != null ? b.y1 : (b.y != null ? b.y : 0);
      bx2 = b.x2 != null ? b.x2 : (bx1 + (b.width || b.w || (b.x2 ? b.x2 - bx1 : 80)));
      by2 = b.y2 != null ? b.y2 : (by1 + (b.height || b.h || (b.y2 ? b.y2 - by1 : 60)));
    }

    const imgW = (t.image_dimensions && t.image_dimensions.width) || (this.rawImage ? this.rawImage.naturalWidth : w) || w;
    const imgH = (t.image_dimensions && t.image_dimensions.height) || (this.rawImage ? this.rawImage.naturalHeight : h) || h;
    const sx = w / imgW;
    const sy = h / imgH;
    const x1 = bx1 * sx;
    const y1 = by1 * sy;
    const x2 = bx2 * sx;
    const y2 = by2 * sy;
    return { x1, y1, x2, y2, bw: Math.max(16, x2 - x1), bh: Math.max(16, y2 - y1), sx, sy };
  }

  _getPolygonCanvasCoords(t, w, h) {
    const coords = this._getTargetCanvasCoords(t, w, h);
    const { x1, y1, bw, bh } = coords;

    const rawPoly = t.customPolygon || t.norm_polygon || t.normPolygon;
    if (rawPoly && Array.isArray(rawPoly) && rawPoly.length >= 3) {
      const isNorm = rawPoly.every(pt => pt[0] <= 1.05 && pt[1] <= 1.05);
      if (isNorm) {
        return rawPoly.map(pt => ({
          x: Math.max(0, Math.min(w, pt[0] * w)),
          y: Math.max(0, Math.min(h, pt[1] * h))
        }));
      }
    }

    if (t.polygon && Array.isArray(t.polygon) && t.polygon.length >= 3) {
      const isNorm = t.polygon.every(pt => pt[0] <= 1.05 && pt[1] <= 1.05);
      if (isNorm) {
        return t.polygon.map(pt => ({
          x: Math.max(0, Math.min(w, pt[0] * w)),
          y: Math.max(0, Math.min(h, pt[1] * h))
        }));
      }
      const imgW = (t.image_dimensions && t.image_dimensions.width) || (this.rawImage ? this.rawImage.naturalWidth : w) || w;
      const imgH = (t.image_dimensions && t.image_dimensions.height) || (this.rawImage ? this.rawImage.naturalHeight : h) || h;
      return t.polygon.map(pt => ({
        x: Math.max(0, Math.min(w, (pt[0] / imgW) * w)),
        y: Math.max(0, Math.min(h, (pt[1] / imgH) * h))
      }));
    }

    // High-fidelity multi-vertex organic morphological model (20 smooth clockwise points)
    const cls = (t.class || t.class_name || "").toLowerCase();
    const pts = [];
    const numPts = 20;
    const cx = x1 + bw * 0.5;
    const cy = y1 + bh * 0.5;
    const rx = bw * 0.46;
    const ry = bh * 0.46;
    const seed = (t.object_id ? t.object_id.charCodeAt(t.object_id.length - 1) : 42);

    for (let i = 0; i < numPts; i++) {
      const angle = (i / numPts) * Math.PI * 2;
      let radMod = 1.0;
      if (cls.includes("net") || cls.includes("gear")) {
        radMod = 0.82 + 0.16 * Math.sin(angle * 3 + seed) + 0.10 * Math.cos(angle * 5 - seed * 0.7);
      } else if (cls.includes("wreck") || cls.includes("ship")) {
        const sinA = Math.sin(angle);
        const bowTaper = (sinA < 0) ? (0.68 + 0.32 * (1 + sinA)) : 1.0;
        radMod = (0.86 + 0.10 * Math.cos(angle * 2)) * bowTaper;
      } else if (cls.includes("pipe") || cls.includes("cable")) {
        radMod = 0.55 + 0.45 * Math.pow(Math.abs(Math.cos(angle)), 0.65);
      } else if (cls.includes("engine") || cls.includes("block")) {
        radMod = 0.86 + 0.11 * Math.cos(angle * 4);
      } else if (cls.includes("riprap") || cls.includes("rock") || cls.includes("boulder")) {
        radMod = 0.84 + 0.15 * Math.sin(angle * 4 + 1.2) + 0.08 * Math.cos(angle * 2);
      } else {
        radMod = 0.85 + 0.13 * Math.sin(angle * 3 + seed * 1.3) + 0.07 * Math.cos(angle * 4);
      }
      const px = Math.max(x1 + bw * 0.02, Math.min(x1 + bw * 0.98, cx + Math.cos(angle) * (rx * radMod)));
      const py = Math.max(y1 + bh * 0.02, Math.min(y1 + bh * 0.98, cy + Math.sin(angle) * (ry * radMod)));
      pts.push({ x: px, y: py });
    }
    return pts;
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Clear whole canvas before drawing with zoom / pan transform
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#030a16";
    ctx.fillRect(0, 0, w, h);
    ctx.restore();

    ctx.save();
    ctx.translate(this.panX, this.panY);
    ctx.scale(this.scale, this.scale);

    // 1. Draw Base Background (Raw or Enhanced or Annotated)
    let baseImg = null;
    if (this.currentMode === "raw") {
      baseImg = this._isImageValid(this.rawImage) ? this.rawImage : (this._isImageValid(this.enhancedImage) ? this.enhancedImage : (this._isImageValid(this.annotatedImage) ? this.annotatedImage : null));
    } else if (this.currentMode === "enhanced") {
      baseImg = this._isImageValid(this.enhancedImage) ? this.enhancedImage : (this._isImageValid(this.rawImage) ? this.rawImage : (this._isImageValid(this.annotatedImage) ? this.annotatedImage : null));
    } else {
      baseImg = this._isImageValid(this.enhancedImage) ? this.enhancedImage : (this._isImageValid(this.rawImage) ? this.rawImage : (this._isImageValid(this.annotatedImage) ? this.annotatedImage : null));
    }

    if (baseImg && this._isImageValid(baseImg)) {
      try {
        ctx.drawImage(baseImg, 0, 0, w, h);
        ctx.fillStyle = "rgba(0, 240, 255, 0.02)";
        ctx.fillRect(0, 0, w, h);
      } catch (err) {
        console.warn("Waterfall drawImage failed:", err);
        this._generateSyntheticWaterfall();
      }
    } else {
      this._generateSyntheticWaterfall();
    }

    // In raw mode without overlays, don't draw bounding layers
    if (this.currentMode === "raw") {
      ctx.restore();
      return;
    }

    // Filter active targets based on dynamic thresholds
    const activeTargets = this.targets.filter(t => this._isTargetActive(t));

    // 2. Render U-Net / Fusion Pixel-Level Segmentation & Node Dots
    activeTargets.forEach(t => {
      const isSelected = (t.object_id === this.selectedTargetId);
      const poly = this._getPolygonCanvasCoords(t, w, h);
      if (!poly || poly.length < 3) return;

      const srcCategory = t.source_category || (t.sources && t.sources.length > 1 ? "BOTH" : (t.sources && t.sources[0] === "unet" ? "UNET_ONLY" : "YOLO_ONLY"));
      const hasUnet = t.sources ? t.sources.includes("unet") : (srcCategory !== "YOLO_ONLY");
      const isFused = (srcCategory === "BOTH") || (t.sources && t.sources.includes("yolo") && t.sources.includes("unet"));

      // Render U-Net Segmentation Mask whenever unet layer is active OR fusion layer is active
      if ((this.layers.unet && hasUnet) || (this.layers.fusion && isFused)) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(poly[i].x, poly[i].y);
        }
        ctx.closePath();

        // 1. Solid Luminous Acoustic Mask Fill (Strictly visible)
        ctx.fillStyle = isSelected 
          ? "rgba(0, 255, 136, 0.42)" 
          : (srcCategory === "UNET_ONLY" ? "rgba(192, 132, 252, 0.32)" : "rgba(0, 240, 255, 0.28)");
        ctx.fill();

        // 2. Crisp Glowing Perimeter Boundary Contour
        const strokeColor = isSelected ? "#00e676" : (srcCategory === "UNET_ONLY" ? "#c084fc" : "#00f0ff");
        ctx.lineWidth = isSelected ? 3.5 : 2.4;
        ctx.strokeStyle = strokeColor;
        ctx.shadowColor = strokeColor;
        ctx.shadowBlur = isSelected ? 16 : 8;
        ctx.stroke();

        // 3. Vertex Node Dots along the contour for selected target or when U-Net layer is active
        const step = isSelected ? 1 : 2;
        for (let i = 0; i < poly.length; i += step) {
          const pt = poly[i];
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, isSelected ? 3.6 : 2.4, 0, Math.PI * 2);
          ctx.fillStyle = isSelected ? "#00e676" : (srcCategory === "UNET_ONLY" ? "#c084fc" : "#00f0ff");
          ctx.fill();
          ctx.lineWidth = 1.0;
          ctx.strokeStyle = "#ffffff";
          ctx.stroke();
        }

        // 4. Clean U-Net Segmentation Tag Badge (shown when selected or when YOLO layer is off)
        if (isSelected || !this.layers.yolo) {
          const minYPt = poly.reduce((minP, p) => p.y < minP.y ? p : minP, poly[0]);
          const uBadgeText = "U-NET SEGMENTATION";
          ctx.font = "bold 9px 'JetBrains Mono', monospace";
          const uBadgeW = ctx.measureText(uBadgeText).width + 8;
          const uBadgeX = Math.max(4, Math.min(w - uBadgeW - 4, minYPt.x - uBadgeW / 2));
          const uBadgeY = Math.max(14, minYPt.y - 6);

          ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
          ctx.fillRect(uBadgeX, uBadgeY - 10, uBadgeW, 12);
          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 1;
          ctx.strokeRect(uBadgeX, uBadgeY - 10, uBadgeW, 12);
          ctx.fillStyle = strokeColor;
          ctx.fillText(uBadgeText, uBadgeX + 4, uBadgeY - 1);
        }

        ctx.restore();
      }
    });

    // Store interactive hit areas for precise canvas click / hover interaction
    this._targetHitBoxes = [];

    // 3. Render YOLO Bold Green Bounding Boxes
    activeTargets.forEach(t => {
      const coords = this._getTargetCanvasCoords(t, w, h);
      const { x1, y1, bw, bh } = coords;

      const isSelected = (t.object_id === this.selectedTargetId);
      const srcCategory = t.source_category || (t.sources && t.sources.length > 1 ? "BOTH" : (t.sources && t.sources[0] === "unet" ? "UNET_ONLY" : "YOLO_ONLY"));
      const hasYolo = t.sources ? t.sources.includes("yolo") : (srcCategory !== "UNET_ONLY");

      // Draw YOLO Bold Green Bounding Box strictly when yolo layer is active AND target has yolo provenance
      if (this.layers.yolo && hasYolo) {
        ctx.save();
        ctx.lineWidth = isSelected ? 3.5 : 2.6;
        ctx.strokeStyle = "#00e676"; // Bright Neon Green
        ctx.shadowColor = "#00e676";
        ctx.shadowBlur = isSelected ? 16 : 8;
        ctx.strokeRect(x1, y1, bw, bh);

        // Corner brackets (Strict 90-degree corner brackets, no diagonal lines)
        const cLen = Math.min(12, bw * 0.22, bh * 0.22);
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(x1, y1 + cLen); ctx.lineTo(x1, y1); ctx.lineTo(x1 + cLen, y1);
        ctx.moveTo(x1 + bw - cLen, y1); ctx.lineTo(x1 + bw, y1); ctx.lineTo(x1 + bw, y1 + cLen);
        ctx.moveTo(x1, y1 + bh - cLen); ctx.lineTo(x1, y1 + bh); ctx.lineTo(x1 + cLen, y1 + bh);
        ctx.moveTo(x1 + bw - cLen, y1 + bh); ctx.lineTo(x1 + bw, y1 + bh); ctx.lineTo(x1 + bw, y1 + bh - cLen);
        ctx.stroke();
        ctx.restore();
      }
    });

    // 4. Smart Collision-Free HUD Label Cards & Badges (Matching Reference Standards)
    const placedBoxes = [];
    let lastRightBottomY = 0;

    activeTargets.forEach(t => {
      const coords = this._getTargetCanvasCoords(t, w, h);
      const { x1, y1, bw, bh } = coords;
      const x2 = x1 + bw;
      const y2 = y1 + bh;

      const isSelected = (t.object_id === this.selectedTargetId);
      const srcCategory = t.source_category || (t.sources && t.sources.length > 1 ? "BOTH" : (t.sources && t.sources[0] === "unet" ? "UNET_ONLY" : "YOLO_ONLY"));
      const hasYolo = t.sources ? t.sources.includes("yolo") : (srcCategory !== "UNET_ONLY");

      // Label text & sizing
      const confPct = Math.round((t.calibrated_confidence || t.confidence || 0) * 100);
      const cleanClass = (t.class_display || t.class || "debris").replace(/_/g, " ").toUpperCase();
      const provBadge = (srcCategory === "BOTH" || (t.sources && t.sources.includes("yolo") && t.sources.includes("unet"))) ? " [YOLO+U-NET]" : (srcCategory === "UNET_ONLY" ? " [U-NET]" : " [YOLO]");
      const badgeText = `${cleanClass} ${confPct}%${provBadge}`;

      ctx.font = "bold 11px 'JetBrains Mono', monospace";
      const tagW = ctx.measureText(badgeText).width + 16;
      const tagH = 22;

      // ID Badge details
      const prioScore = t.priority_score || 85;
      const prioLevel = t.priority_level || (t.risk_score || "HIGH");
      const idText = `${t.object_id} — ${prioScore} — ${prioLevel}`;
      ctx.font = "bold 10px 'JetBrains Mono', monospace";
      const idW = ctx.measureText(idText).width + 12;
      const idH = 16;
      const prioCol = (prioScore >= 81) ? "#ff3366" : ((prioScore >= 61) ? "#ff9100" : "#00f0ff");

      // Verification Badge details
      const vStatus = t.verification_status || "confirmed";
      const isConfirmed = (vStatus === "confirmed");
      const vBadgeColor = isConfirmed ? "#00e676" : "#ffab00";
      const vBadgeText = isConfirmed ? "CONFIRMED" : "SUSPICIOUS";
      ctx.font = "bold 9px 'JetBrains Mono', monospace";
      const vW = ctx.measureText(vBadgeText).width + 10;
      const vH = 16;

      const labelPos = t.label_pos || t.labelPos || {};
      const isRightSide = (labelPos.side === "right");

      let cardX, cardY;

      if (isRightSide) {
        // Offset to the right in clean vertical column with leader line (Image 2 standard)
        cardX = Math.max(x2 + 22, Math.round(w * 0.38));
        if (labelPos.alignX !== undefined) {
          cardX = Math.round(labelPos.alignX * w);
        }

        let targetY = (labelPos.alignY !== undefined) ? (labelPos.alignY * h - tagH / 2) : (y1 + bh * 0.45 - tagH / 2);
        // Ensure no overlap with prior right-side label
        if (targetY < lastRightBottomY + 8) {
          targetY = lastRightBottomY + 8;
        }
        cardY = Math.max(10, Math.min(h - tagH - 24, Math.round(targetY)));
        lastRightBottomY = cardY + tagH + idH + 4;

        // Leader line from target contact to label pill
        ctx.save();
        const leaderStroke = isSelected ? "#00e676" : "#00f0ff";
        ctx.strokeStyle = leaderStroke;
        ctx.lineWidth = isSelected ? 2.2 : 1.5;
        ctx.shadowColor = leaderStroke;
        ctx.shadowBlur = isSelected ? 10 : 5;

        const anchorX = x2;
        const anchorY = y1 + Math.min(bh * 0.5, 20);

        // Anchor node dot on bbox edge
        ctx.beginPath();
        ctx.arc(anchorX, anchorY, 3.2, 0, Math.PI * 2);
        ctx.fillStyle = leaderStroke;
        ctx.fill();

        // Connector path: subtle horizontal dogleg
        ctx.beginPath();
        ctx.moveTo(anchorX, anchorY);
        const midX = anchorX + 14;
        ctx.lineTo(midX, anchorY);
        ctx.lineTo(cardX - 4, cardY + tagH / 2);
        ctx.stroke();
        ctx.restore();

      } else {
        // Standard top placement with collision avoidance
        let candX = Math.max(4, Math.min(w - tagW - 4, x1));
        let candY = y1 - tagH - 4;

        if (candY < 6) {
          candY = y1 + bh + 4; // if near top, flip below
        }

        // Detect collisions with previously placed boxes
        for (let i = 0; i < placedBoxes.length; i++) {
          const pb = placedBoxes[i];
          const overlapX = candX < pb.x + pb.w && candX + tagW > pb.x;
          const overlapY = candY < pb.y + pb.h && candY + tagH > pb.y;
          if (overlapX && overlapY) {
            // Shift vertically to avoid overlap
            candY = pb.y - tagH - 4;
            if (candY < 6) {
              candY = pb.y + pb.h + 4;
            }
          }
        }
        cardX = candX;
        cardY = candY;
      }

      // Record bounds for hit-testing and collision detection
      const totalCardW = Math.max(tagW, idW + vW + 8);
      const totalCardH = tagH + (this.layers.ids || this.layers.verify ? idH + 4 : 0);
      placedBoxes.push({ x: cardX, y: cardY, w: totalCardW, h: totalCardH });
      this._targetHitBoxes.push({
        id: t.object_id,
        bbox: { x1, y1, x2, y2 },
        card: { x1: cardX, y1: cardY, x2: cardX + totalCardW, y2: cardY + totalCardH }
      });

      // 1. Draw Magenta Label Pill (when YOLO layer active)
      if (this.layers.yolo && hasYolo) {
        ctx.save();
        ctx.fillStyle = "#e00080";
        ctx.fillRect(cardX, cardY, tagW, tagH);

        ctx.strokeStyle = isSelected ? "#00e676" : "#ffffff";
        ctx.lineWidth = isSelected ? 2 : 1;
        if (isSelected) {
          ctx.shadowColor = "#00e676";
          ctx.shadowBlur = 10;
        }
        ctx.strokeRect(cardX, cardY, tagW, tagH);

        ctx.font = "bold 11px 'JetBrains Mono', monospace";
        ctx.fillStyle = "#ffffff";
        ctx.shadowBlur = 0;
        ctx.fillText(badgeText, cardX + 8, cardY + 15);
        ctx.restore();
      }

      // 2. Draw ID Badge and Verification Badge
      if (isRightSide) {
        // In right-side offset mode, render ID Badge and Verification Badge directly below the magenta pill
        const subY = cardY + tagH + 3;

        if (this.layers.ids && subY + idH <= h) {
          ctx.save();
          ctx.fillStyle = "rgba(4, 10, 24, 0.94)";
          ctx.fillRect(cardX, subY, idW, idH);
          ctx.strokeStyle = prioCol;
          ctx.lineWidth = 1;
          ctx.strokeRect(cardX, subY, idW, idH);

          ctx.font = "bold 10px 'JetBrains Mono', monospace";
          ctx.fillStyle = prioCol;
          ctx.fillText(idText, cardX + 6, subY + 12);
          ctx.restore();
        }

        if (this.layers.verify && subY + vH <= h) {
          ctx.save();
          const vX = cardX + (this.layers.ids ? idW + 4 : 0);
          ctx.fillStyle = "rgba(10, 15, 26, 0.92)";
          ctx.fillRect(vX, subY, vW, vH);
          ctx.strokeStyle = vBadgeColor;
          ctx.lineWidth = 1;
          ctx.strokeRect(vX, subY, vW, vH);

          ctx.font = "bold 9px 'JetBrains Mono', monospace";
          ctx.fillStyle = vBadgeColor;
          ctx.fillText(vBadgeText, vX + 5, subY + 12);
          ctx.restore();
        }
      } else {
        // Top placement: ID below bounding box, Verification inside bottom-right or top-right
        if (this.layers.ids) {
          ctx.save();
          let idY = y1 + bh + 3;
          if (idY + idH > h) idY = y1 - idH - 2;

          ctx.fillStyle = "rgba(4, 10, 24, 0.94)";
          ctx.fillRect(x1, idY, idW, idH);
          ctx.strokeStyle = prioCol;
          ctx.lineWidth = 1;
          ctx.strokeRect(x1, idY, idW, idH);

          ctx.font = "bold 10px 'JetBrains Mono', monospace";
          ctx.fillStyle = prioCol;
          ctx.fillText(idText, x1 + 6, idY + 12);
          ctx.restore();
        }

        if (this.layers.verify) {
          ctx.save();
          const vX = Math.max(x1, x1 + bw - vW - 3);
          const vY = (bh >= 36) ? (y1 + bh - 18) : (y1 + 3);

          ctx.fillStyle = "rgba(10, 15, 26, 0.92)";
          ctx.fillRect(vX, vY, vW, vH);
          ctx.strokeStyle = vBadgeColor;
          ctx.lineWidth = 1;
          ctx.strokeRect(vX, vY, vW, vH);

          ctx.font = "bold 9px 'JetBrains Mono', monospace";
          ctx.fillStyle = vBadgeColor;
          ctx.fillText(vBadgeText, vX + 5, vY + 12);
          ctx.restore();
        }
      }
    });

    ctx.restore();
  }

  _initEvents() {
    const getCanvasPoint = (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      const rawX = (e.clientX - rect.left) * scaleX;
      const rawY = (e.clientY - rect.top) * scaleY;
      const worldX = (rawX - this.panX) / this.scale;
      const worldY = (rawY - this.panY) / this.scale;
      return { rawX, rawY, worldX, worldY };
    };

    const findHitTarget = (pt) => {
      if (this._targetHitBoxes && this._targetHitBoxes.length > 0) {
        const hit = this._targetHitBoxes.find(hb => {
          const inBbox = pt.worldX >= hb.bbox.x1 && pt.worldX <= hb.bbox.x2 && pt.worldY >= hb.bbox.y1 && pt.worldY <= hb.bbox.y2;
          const inCard = hb.card && pt.worldX >= hb.card.x1 && pt.worldX <= hb.card.x2 && pt.worldY >= hb.card.y1 && pt.worldY <= hb.card.y2;
          return inBbox || inCard;
        });
        if (hit) {
          const found = this.targets.find(t => t.object_id === hit.id);
          if (found) return found;
        }
      }
      return this.targets.find(t => {
        const coords = this._getTargetCanvasCoords(t, this.canvas.width, this.canvas.height);
        return pt.worldX >= coords.x1 && pt.worldX <= coords.x2 && pt.worldY >= coords.y1 && pt.worldY <= coords.y2;
      });
    };

    // Mouse wheel zoom
    this.canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const pt = getCanvasPoint(e);
      const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
      this.zoomAt(pt.rawX, pt.rawY, zoomFactor);
    }, { passive: false });

    // Drag to pan
    this.canvas.addEventListener('mousedown', (e) => {
      this.isDragging = true;
      this.hasMoved = false;
      this.dragStartX = e.clientX;
      this.dragStartY = e.clientY;
      this.dragStartPanX = this.panX;
      this.dragStartPanY = this.panY;
      this.canvas.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) {
        const rect = this.canvas.getBoundingClientRect();
        if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
          const pt = getCanvasPoint(e);
          const hit = findHitTarget(pt);
          if (hit) {
            this.canvas.style.cursor = 'pointer';
            if (window.app && window.app.selectedTargetId !== hit.object_id) {
              window.app.onTargetSelected(hit.object_id, { fly: false });
            }
          } else {
            this.canvas.style.cursor = this.scale > 1.05 ? 'grab' : 'default';
          }
        }
        return;
      }

      const dx = e.clientX - this.dragStartX;
      const dy = e.clientY - this.dragStartY;
      if (Math.hypot(dx, dy) > 4) {
        this.hasMoved = true;
      }

      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;

      this.panX = this.dragStartPanX + dx * scaleX;
      this.panY = this.dragStartPanY + dy * scaleY;
      this._clampPan();
      this.render();
    });

    window.addEventListener('mouseup', (e) => {
      if (this.isDragging) {
        this.isDragging = false;
        this.canvas.style.cursor = this.scale > 1.05 ? 'grab' : 'default';
      }
    });

    // Click selection (only if not dragged)
    this.canvas.addEventListener('click', (e) => {
      if (this.hasMoved) return;
      const pt = getCanvasPoint(e);
      const clicked = findHitTarget(pt);
      if (clicked && window.app) {
        window.app.onTargetSelected(clicked.object_id, { fly: true, force: true });
      }
    });

    // Double click to zoom in or reset
    this.canvas.addEventListener('dblclick', (e) => {
      e.preventDefault();
      if (this.scale > 1.8) {
        this.resetZoom();
      } else {
        const pt = getCanvasPoint(e);
        this.zoomAt(pt.rawX, pt.rawY, 1.8);
      }
    });
  }
}

window.WaterfallViewer = WaterfallViewer;
