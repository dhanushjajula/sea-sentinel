# Sea Sentinel — Frontend Review Intelligence Module

## Overview
This folder houses the frontend user interface components and state handlers for:
1. **Structured Review Modal**: Ingests annotator feedback, error classification, mask/box corrections, and verifier confidence.
2. **Adaptive Learning Command Center**: Displays real-time KPIs, Top Recurring Failures, Active Learning Queue, Candidate Classes, and Champion vs Challenger performance diffs.

## Associated Files
- Modal DOM Elements: Defined in `frontend/index.html` (`#feedbackModal`, `#learningModal`)
- API Client: Defined in `frontend/js/api.js`
- UI Controllers: Defined in `frontend/js/app.js`
- Styles: Defined in `frontend/css/style.css`
