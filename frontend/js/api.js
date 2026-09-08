/**
 * Sea Sentinel: API & Data Service
 * Connects to FastAPI backend (/api/...) with seamless offline/mock data fallback.
 */

const API_BASE_URL = "http://localhost:8000";

// Benchmark test dataset for immediate demonstration (NOAA Survey H11584, Gulf of Mexico, WGS84 UTM 16N)
const BENCHMARK_TARGETS = [
  {
    object_id: "TGT_001",
    class: "fishing_net",
    raw_confidence: 0.88,
    calibrated_confidence: 0.81,
    anomaly_status: "confirmed_debris",
    risk_score: "HIGH",
    latitude: 30.171543,
    longitude: -87.823543,
    lat: 30.171543,
    lon: -87.823543,
    length_m: 14.2,
    width_m: 5.8,
    area_sq_m: 82.36,
    reconstruction_error: 0.1245,
    shadow_verified: true,
    is_rock_cluster: false,
    position_uncertainty_m: 1.5,
    georeferencing_case: "A",
    coordinate_system: "WGS84 / UTM Zone 16N (EPSG:32616)",
    dataset_profile: "NOAA NOS Hydrographic Survey H11584 (Gulf of Mexico, UTM 16N, 1.0m/px)",
    pixel_bbox: { x1: 280, y1: 140, x2: 430, y2: 260 },
    explanation: {
      morphology_note: "Dispersed irregular acoustic backscatter mesh typical of synthetic polymer netting.",
      action_recommendation: "PRIORITY INTERVENTION: Schedule targeted ROV/AUV optical inspection and recovery planning to prevent wildlife entanglement.",
      executive_narrative: "Target TGT_001 categorized as 'fishing_net' with 81.0% calibrated confidence in NOAA survey H11584. Pronounced acoustic shadow confirms elevated benthic relief. Assigned HIGH ecological hazard."
    }
  },
  {
    object_id: "TGT_002",
    class: "pipeline_or_cable",
    raw_confidence: 0.82,
    calibrated_confidence: 0.77,
    anomaly_status: "confirmed_debris",
    risk_score: "HIGH",
    latitude: 30.172850,
    longitude: -87.821940,
    lat: 30.172850,
    lon: -87.821940,
    length_m: 38.6,
    width_m: 2.1,
    area_sq_m: 81.06,
    reconstruction_error: 0.1082,
    shadow_verified: true,
    is_rock_cluster: false,
    position_uncertainty_m: 1.5,
    georeferencing_case: "A",
    coordinate_system: "WGS84 / UTM Zone 16N (EPSG:32616)",
    dataset_profile: "NOAA NOS Hydrographic Survey H11584 (Gulf of Mexico, UTM 16N, 1.0m/px)",
    pixel_bbox: { x1: 680, y1: 220, x2: 1040, y2: 270 },
    explanation: {
      morphology_note: "Continuous linear/tubular acoustic signature with high aspect ratio.",
      action_recommendation: "ASSET MONITORING: Log pipeline corridor coordinate; inspect for bottom-trawling anchor drag damage.",
      executive_narrative: "Target TGT_002 categorized as 'pipeline_or_cable' with 77.0% calibrated confidence in Mississippi fairway corridor. Continuous linear backscatter with trailing shadow. Assigned HIGH navigation hazard."
    }
  },
  {
    object_id: "TGT_003_ROCK",
    class: "riprap_debris",
    raw_confidence: 0.58,
    calibrated_confidence: 0.04,
    anomaly_status: "noise_rejected",
    risk_score: "LOW",
    latitude: 30.170120,
    longitude: -87.825100,
    lat: 30.170120,
    lon: -87.825100,
    length_m: 3.2,
    width_m: 2.8,
    area_sq_m: 8.96,
    reconstruction_error: 0.0612,
    shadow_verified: false,
    is_rock_cluster: true,
    position_uncertainty_m: 1.5,
    georeferencing_case: "A",
    coordinate_system: "WGS84 / UTM Zone 16N (EPSG:32616)",
    dataset_profile: "NOAA NOS Hydrographic Survey H11584 (Gulf of Mexico, UTM 16N, 1.0m/px)",
    pixel_bbox: { x1: 150, y1: 300, x2: 190, y2: 340 },
    explanation: {
      morphology_note: "Dense clustered point highlights characteristic of natural rock moraines.",
      action_recommendation: "NATURAL GEOLOGY: Filtered by DBSCAN spatial cluster suppression; no action required.",
      executive_narrative: "Target TGT_003_ROCK identified as natural geological formation; suppressed by DBSCAN density filter (confidence penalized to 4.0%)."
    }
  },
  {
    object_id: "TGT_004",
    class: "shipwreck_fragment",
    raw_confidence: 0.74,
    calibrated_confidence: 0.69,
    anomaly_status: "suspicious_anomaly",
    risk_score: "MEDIUM",
    latitude: 30.169500,
    longitude: -87.820500,
    lat: 30.169500,
    lon: -87.820500,
    length_m: 11.5,
    width_m: 7.2,
    area_sq_m: 82.80,
    reconstruction_error: 0.0965,
    shadow_verified: true,
    is_rock_cluster: false,
    position_uncertainty_m: 1.5,
    georeferencing_case: "A",
    coordinate_system: "WGS84 / UTM Zone 16N (EPSG:32616)",
    dataset_profile: "NOAA NOS Hydrographic Survey H11584 (Gulf of Mexico, UTM 16N, 1.0m/px)",
    pixel_bbox: { x1: 520, y1: 80, x2: 640, y2: 160 },
    explanation: {
      morphology_note: "Rectilinear geometric acoustic highlight with distinct relief shadow.",
      action_recommendation: "SUBSEA HAZARD: Log target for subsequent multi-beam verification pass.",
      executive_narrative: "Target TGT_004 categorized as 'shipwreck_fragment' (69.0% calibrated). Autoencoder MSE (0.0965) confirms anomaly. Assigned MEDIUM risk."
    }
  }
];

class SeaSentinelAPI {
  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  async checkHealth() {
    try {
      const res = await fetch(`${this.baseUrl}/api/health`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) return await res.json();
    } catch (e) {
      // Backend offline
    }
    return { status: "offline", fallback_mode: true };
  }

  async fetchSamples() {
    try {
      const res = await fetch(`${this.baseUrl}/api/samples`, { signal: AbortSignal.timeout(2500) });
      if (res.ok) {
        const data = await res.json();
        if (data && data.samples && data.samples.length > 0) {
          return data.samples;
        }
      }
    } catch (e) {
      console.warn("Backend /api/samples unreachable, using fallback sample catalog.");
    }

    return [
      {
        id: "noaa_h11584_gulf",
        name: "NOAA Survey H11584 Mosaic (Gulf of Mexico)",
        category: "georeferenced_mosaic",
        risk_hint: "HIGH",
        filename: "noaa_h11584_gulf_sample.tif",
        description: "NOAA NOS Hydrographic Survey H11584 GeoTIFF mosaic in Gulf of Mexico. Authentic WGS84 UTM 16N coordinates (1.0m/px).",
        georef_case: "A",
        simulated_coords: { lat: 30.171543, lon: -87.823543 }
      },
      {
        id: "usgs_14bim05_breton",
        name: "USGS DS 1005 Barrier Islands (Breton Sound LA)",
        category: "georeferenced_mosaic",
        risk_hint: "MEDIUM",
        filename: "usgs_14bim05_breton_sample.tif",
        description: "USGS DS 1005 high-resolution side-scan sonar mosaic near Breton & Gosier Islands, Louisiana. Authentic WGS84 UTM 16N coordinates (0.50m/px).",
        georef_case: "A",
        simulated_coords: { lat: 29.425020, lon: -89.193541 }
      },
      {
        id: "towfish_mission_case_b",
        name: "Towfish Survey + Nav Telemetry (Case B)",
        category: "sonar_waterfall",
        risk_hint: "HIGH",
        filename: "towfish_mission_case_b.png",
        description: "Acoustic waterfall accompanied by navigation log (latitude, longitude, heading, altitude). Geodesic slant-to-ground range forward projection.",
        georef_case: "B",
        simulated_coords: { lat: 30.193838, lon: -87.880987 }
      },
      {
        id: "china_offshore_quanzhou_net",
        name: "China Offshore SSS-AI (Zenodo 20048164)",
        category: "fishing_net",
        risk_hint: "HIGH",
        filename: "china_offshore_quanzhou_net.jpg",
        description: "Standardized cropped SSS image chip from Zenodo 20048164. Release contains image pixels only; no coordinates provided. Case C Unreferenced.",
        georef_case: "C",
        simulated_coords: null
      },
      {
        id: "china_offshore_dongying_pipe",
        name: "China Offshore SSS-AI Pipeline (Zenodo 20048164)",
        category: "pipeline_or_cable",
        risk_hint: "HIGH",
        filename: "china_offshore_dongying_pipeline.jpg",
        description: "Continuous linear acoustic signature from Zenodo 20048164. No telemetry provided in dataset; coordinates are strictly withheld.",
        georef_case: "C",
        simulated_coords: null
      }
    ];
  }

  async uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${this.baseUrl}/api/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      const error = new Error(err.detail || `Upload failed with status ${res.status}`);
      error.status = res.status;
      error.isSonar = false;
      error.detail = err.detail;
      throw error;
    }

    return await res.json();
  }

  getMockAnalysisResult(imagePath) {
    return {
      analysis_id: "SURVEY_DEMO_BENCHMARK",
      status: "success",
      is_sonar: true,
      detections_count: BENCHMARK_TARGETS.length,
      detections: BENCHMARK_TARGETS,
      summary: {
        total_targets: BENCHMARK_TARGETS.length,
        critical_hazards: 2,
        confirmed_debris: 2,
        georeferenced_targets: BENCHMARK_TARGETS.length,
        average_confidence: 0.77
      },
      nav_log: {
        heading: 85.0,
        altitude_m: 12.0,
        latitude: 30.171543,
        longitude: -87.823543
      }
    };
  }

  async analyzeImage(imagePath, rasterMeta = null, navLog = null) {
    const payload = {
      image_path: imagePath,
      raster_meta: rasterMeta,
      nav_log: navLog
    };

    try {
      const res = await fetch(`${this.baseUrl}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Analysis failed" }));
        const error = new Error(err.detail || `Analysis failed with status ${res.status}`);
        error.status = res.status;
        error.isSonar = false;
        error.detail = err.detail;
        throw error;
      }

      return await res.json();
    } catch (e) {
      // If server rejected non-sonar image, rethrow so UI can display rejected state
      if (e.status === 400 || (e.detail && e.detail.toLowerCase().includes("non-sonar"))) {
        throw e;
      }
      console.warn("Backend /api/analyze unavailable, providing benchmark geospatial survey results:", e);
      return this.getMockAnalysisResult(imagePath);
    }
  }

  async getSurveyTargets() {
    try {
      const res = await fetch(`${this.baseUrl}/api/geospatial`, { signal: AbortSignal.timeout(2000) });
      if (res.ok) {
        const data = await res.json();
        if (data && data.targets && data.targets.length > 0) {
          return data.targets;
        }
      }
    } catch (e) {
      console.warn("Geospatial targets API not reachable:", e);
    }
    return BENCHMARK_TARGETS;
  }

  async submitFeedback(analysisId, objectId, comment, correctedClassOverride = null) {
    const payload = {
      analysis_id: analysisId,
      object_id: objectId,
      comment: comment,
      corrected_class_override: correctedClassOverride
    };

    const res = await fetch(`${this.baseUrl}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Feedback submission failed" }));
      throw new Error(err.detail || "Failed to submit feedback");
    }

    return await res.json();
  }

  async getFeedbackMemory() {
    try {
      const res = await fetch(`${this.baseUrl}/api/feedback/memory`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Feedback memory endpoint unreachable:", e);
    }
    return { status: "error", corrections: [], stats: {} };
  }

  async triggerFineTuning(epochs = 5, batchSize = 8, dryRun = false) {
    const res = await fetch(`${this.baseUrl}/api/feedback/train`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ epochs, batch_size: batchSize, dry_run: dryRun })
    });
    return await res.json();
  }

  async getLearnerStatus() {
    try {
      const res = await fetch(`${this.baseUrl}/api/feedback/status`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Feedback status unreachable:", e);
    }
    return { is_training: false };
  }
}

window.apiService = new SeaSentinelAPI();
