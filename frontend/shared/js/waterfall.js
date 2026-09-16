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

    if (t.norm_polygon && Array.isArray(t.norm_polygon) && t.norm_polygon.length >= 3) {
      const isNorm = t.norm_polygon.every(pt => pt[0] <= 1.05 && pt[1] <= 1.05);
      if (isNorm) {
        return t.norm_polygon.map(pt => ({
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

    return [
      { x: x1 + bw * 0.18, y: y1 + bh * 0.06 },
      { x: x1 + bw * 0.72, y: y1 + bh * 0.08 },
      { x: x1 + bw * 0.96, y: y1 + bh * 0.38 },
      { x: x1 + bw * 0.90, y: y1 + bh * 0.82 },
      { x: x1 + bw * 0.58, y: y1 + bh * 0.96 },
      { x: x1 + bw * 0.20, y: y1 + bh * 0.92 },
      { x: x1 + bw * 0.04, y: y1 + bh * 0.62 },
      { x: x1 + bw * 0.06, y: y1 + bh * 0.25 }
    ];
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

    // 2. Render U-Net / Fusion Pixel-Level Segmentation & Node Dots
    this.targets.forEach(t => {
      const isSelected = (t.object_id === this.selectedTargetId);
      const poly = this._getPolygonCanvasCoords(t, w, h);
      if (!poly || poly.length < 3) return;

      // (A) Fused Boundaries Translucent Fill Mask
      if (this.layers.fusion) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(poly[i].x, poly[i].y);
        }
        ctx.closePath();
        ctx.fillStyle = isSelected ? "rgba(0, 255, 128, 0.32)" : "rgba(0, 240, 255, 0.24)";
        ctx.fill();
        ctx.restore();
      }

      // (B) U-Net Crisp Perimeter Contour Lines & Keypoint Node Dots
      if (this.layers.unet) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(poly[0].x, poly[0].y);
        for (let i = 1; i < poly.length; i++) {
          ctx.lineTo(poly[i].x, poly[i].y);
        }
        ctx.closePath();
        ctx.lineWidth = isSelected ? 3.0 : 2.2;
        ctx.strokeStyle = isSelected ? "#00e676" : "#00f0ff";
        ctx.shadowColor = isSelected ? "#00e676" : "#00f0ff";
        ctx.shadowBlur = isSelected ? 12 : 6;
        ctx.stroke();

        // Draw clean vertex dots
        for (let i = 0; i < poly.length; i++) {
          const pt = poly[i];
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, isSelected ? 4.5 : 3.5, 0, Math.PI * 2);
          ctx.fillStyle = isSelected ? "#00e676" : "#00f0ff";
          ctx.fill();
          ctx.lineWidth = 1.2;
          ctx.strokeStyle = "#ffffff";
          ctx.stroke();
        }
        ctx.restore();
      }
    });

    // 3. Render YOLO Bold Green Bounding Boxes & Magenta Label Tags
    this.targets.forEach(t => {
      const coords = this._getTargetCanvasCoords(t, w, h);
      const { x1, y1, bw, bh } = coords;

      const isSelected = (t.object_id === this.selectedTargetId);
      const srcCategory = t.source_category || (t.sources && t.sources.length > 1 ? "BOTH" : (t.sources && t.sources[0] === "unet" ? "UNET_ONLY" : "YOLO_ONLY"));
      const hasYolo = t.sources ? t.sources.includes("yolo") : (srcCategory !== "UNET_ONLY");

      // Draw YOLO Bold Green Bounding Box
      if (this.layers.yolo && (hasYolo || this.layers.fusion || this.layers.unet)) {
        ctx.save();
        ctx.lineWidth = isSelected ? 3.5 : 2.8;
        ctx.strokeStyle = "#00e676"; // Bright Neon Green
        ctx.shadowColor = "#00e676";
        ctx.shadowBlur = isSelected ? 16 : 8;
        ctx.strokeRect(x1, y1, bw, bh);

        // Corner brackets
        const cLen = Math.min(12, bw * 0.22, bh * 0.22);
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(x1, y1 + cLen); ctx.lineTo(x1, y1); ctx.lineTo(x1 + cLen, y1);
        ctx.moveTo(x1 + bw - cLen, y1); ctx.lineTo(x1 + bw, y1); ctx.lineTo(x1 + bw, y1 + cLen);
        ctx.moveTo(x1 + bh - cLen, y1); ctx.lineTo(x1, y1 + bh); ctx.lineTo(x1 + cLen, y1 + bh);
        ctx.moveTo(x1 + bw - cLen, y1 + bh); ctx.lineTo(x1 + bw, y1 + bh); ctx.lineTo(x1 + bw, y1 + bh - cLen);
        ctx.stroke();

        // Magenta Label Pill Badge
        const confPct = Math.round((t.calibrated_confidence || t.confidence || 0) * 100);
        const cleanClass = (t.class_display || t.class || "debris").replace(/_/g, " ").toUpperCase();
        const provBadge = srcCategory === "BOTH" ? " [YOLO+U-NET]" : (srcCategory === "UNET_ONLY" ? " [U-NET]" : " [YOLO]");
        const badgeText = `${cleanClass} ${confPct}%${provBadge}`;

        ctx.font = "bold 11px 'JetBrains Mono', monospace";
        const tagW = ctx.measureText(badgeText).width + 16;
        const tagH = 22;
        const tagY = Math.max(0, y1 - tagH + 2);

        ctx.fillStyle = "#e00080";
        ctx.fillRect(x1, tagY, tagW, tagH);

        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.strokeRect(x1, tagY, tagW, tagH);

        ctx.fillStyle = "#ffffff";
        ctx.fillText(badgeText, x1 + 8, tagY + 15);

        ctx.restore();
      }

      // Draw Verification Indicator Badge
      if (this.layers.verify) {
        ctx.save();
        const vStatus = t.verification_status || "confirmed";
        const isConfirmed = (vStatus === "confirmed");
        const badgeColor = isConfirmed ? "#00e676" : "#ffab00";
        const badgeText = isConfirmed ? "VERIFIED" : "SUSPICIOUS";

        ctx.font = "bold 9px 'JetBrains Mono', monospace";
        const bWidth = ctx.measureText(badgeText).width + 8;
        ctx.fillStyle = "rgba(10, 15, 26, 0.92)";
        ctx.fillRect(x1 + bw - bWidth - 2, y1 + bh - 16, bWidth, 14);
        ctx.strokeStyle = badgeColor;
        ctx.lineWidth = 1;
        ctx.strokeRect(x1 + bw - bWidth - 2, y1 + bh - 16, bWidth, 14);
        ctx.fillStyle = badgeColor;
        ctx.fillText(badgeText, x1 + bw - bWidth + 2, y1 + bh - 6);
        ctx.restore();
      }

      // Draw Target IDs and Priority / Risk Level
      if (this.layers.ids) {
        ctx.save();
        const prioScore = t.priority_score || 85;
        const prioLevel = t.priority_level || (t.risk_score || "HIGH");
        const label = `${t.object_id} — ${prioScore} — ${prioLevel}`;

        ctx.font = "bold 10px 'JetBrains Mono', monospace";
        const textW = ctx.measureText(label).width;
        const idY = y1 + bh + 14;

        if (idY < h) {
          const badgeCol = (prioScore >= 81) ? "#ff3366" : ((prioScore >= 61) ? "#ff9100" : "#00f0ff");
          ctx.fillStyle = "rgba(4, 10, 24, 0.94)";
          ctx.fillRect(x1, y1 + bh + 2, textW + 10, 16);
          ctx.strokeStyle = badgeCol;
          ctx.lineWidth = 1;
          ctx.strokeRect(x1, y1 + bh + 2, textW + 10, 16);
          ctx.fillStyle = badgeCol;
          ctx.fillText(label, x1 + 5, y1 + bh + 14);
        }
        ctx.restore();
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
