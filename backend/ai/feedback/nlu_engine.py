"""
Feedback Natural Language Understanding (NLU) Engine
Understands human natural language feedback, analyzes semantic corrections,
handles negation and contrastive phrases, and extracts the standardized
hydrographic class and operational rationale.
"""

from typing import Dict, Any, Optional, Tuple, List
import re


class FeedbackNLUEngine:
    """
    Parses natural language comments from hydrographers and operators
    to identify intended target reclassification or false-alarm suppression.
    """

    # Harmonized 5 Authorized Side-Scan Sonar Debris Classes
    CLASS_REGISTRY = {
        0: "fishing_net",
        1: "pipeline_or_cable",
        2: "shipwreck_fragment",
        3: "engine_debris",
        4: "riprap_debris"
    }

    CLASS_NAME_TO_ID = {v: k for k, v in CLASS_REGISTRY.items()}

    # Synonyms and domain terminology mapping
    SYNONYM_MAP = {
        "fishing_net": [
            "fishing net", "fishing_net", "ghost net", "ghost_net", "net", "nets",
            "gillnet", "trawl", "trawler net", "mesh", "nylon net", "synthetic net",
            "tangled net", "rope tangle", "fishing gear", "derelict gear", "webbing"
        ],
        "pipeline_or_cable": [
            "pipeline or cable", "pipeline_or_cable", "pipeline", "pipe", "pipes",
            "cable", "cables", "power cable", "telecom cable", "submarine cable",
            "conduit", "undersea pipe", "linear pipe", "transmission line", "hose"
        ],
        "shipwreck_fragment": [
            "shipwreck fragment", "shipwreck_fragment", "shipwreck", "wreck",
            "wreckage", "ship", "boat", "vessel", "hull", "keel", "mast",
            "timber", "ribs", "sunken vessel", "barge", "hull fragment"
        ],
        "engine_debris": [
            "engine debris", "engine_debris", "engine", "motor", "outboard motor",
            "engine block", "cylinder", "machinery", "machine", "mechanical",
            "pump", "generator", "propeller", "turbine", "gearbox", "metallic part"
        ],
        "riprap_debris": [
            "riprap debris", "riprap_debris", "riprap", "rip-rap", "rock", "rocks",
            "boulder", "boulders", "stone", "stones", "rubble", "seabed rock",
            "geological formation", "bedrock", "moraine", "breakwater rock"
        ]
    }

    # False-positive / background indicators
    FALSE_ALARM_TERMS = [
        "false alarm", "false positive", "false detection", "not debris",
        "nothing", "empty seabed", "background noise", "sediment",
        "sand ripple", "acoustic artifact", "sonar glare", "clear seabed",
        "natural seafloor", "just sand", "just water"
    ]

    def __init__(self):
        # Precompile regex search patterns for each class
        self._class_patterns = {}
        for cls_name, synonyms in self.SYNONYM_MAP.items():
            # Sort by length descending to match longest phrase first (e.g. 'ghost net' before 'net')
            sorted_syns = sorted(synonyms, key=lambda s: len(s), reverse=True)
            escaped = [re.escape(s) for s in sorted_syns]
            pattern = re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)
            self._class_patterns[cls_name] = pattern

    def parse_feedback(
        self,
        comment: Optional[str] = None,
        current_model_class: Optional[str] = None,
        text: Optional[str] = None,
        original_class: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses free-form feedback text to extract the intended correction.

        Handles patterns:
          - "This is actually a fishing net, not a pipeline"
          - "It's a shipwreck fragment, wrong detection"
          - "Not a rock, it is an engine block"
          - "Change to cable or pipeline"
          - "False alarm, this is just natural seabed rock"
        """
        input_text = comment if comment is not None else (text or "")
        current_model_class = original_class if original_class is not None else current_model_class

        if not input_text or not input_text.strip():
            return {
                "valid": False,
                "error": "Feedback comment is empty.",
                "original_class": current_model_class,
                "corrected_class": current_model_class,
                "class_id": self.CLASS_NAME_TO_ID.get(current_model_class, 0),
                "corrected_class_id": self.CLASS_NAME_TO_ID.get(current_model_class, 0),
                "correction_type": "none",
                "extracted_reason": "No comment provided.",
                "rationale": "No comment provided."
            }

        text = input_text.strip()
        text_lower = text.lower()

        # 1. Check for false alarm / background declaration
        is_false_alarm = any(term in text_lower for term in self.FALSE_ALARM_TERMS)

        # 2. Check for contrastive negation patterns:
        # e.g., "not a (X), it is (Y)" or "not (X) but (Y)"
        negation_match = re.search(
            r'(?:not|isn\'t|is not)\s+(?:a|an|the)?\s*([a-z\s_]+?)\s*(?:,|;|\.|\s+but|\s+actually|\s+it\'s|\s+it is|\s+rather|\s+instead of|\s+instead)\s+(?:a|an|the)?\s*([a-z\s_]+)',
            text_lower
        )

        detected_candidate_class = None
        negated_candidate_class = None

        if negation_match:
            negated_part = negation_match.group(1).strip()
            asserted_part = negation_match.group(2).strip()

            neg_class = self._extract_class_from_text(negated_part)
            pos_class = self._extract_class_from_text(asserted_part)

            if pos_class:
                detected_candidate_class = pos_class
                negated_candidate_class = neg_class or current_model_class

        # Inverse contrastive pattern: "It is (Y), not (X)"
        if not detected_candidate_class:
            inv_match = re.search(
                r'(?:it\'s|it is|actually|this is)\s+(?:a|an|the)?\s*([a-z\s_]+?)\s*(?:,|;|\s+and)?\s+(?:not|not a|not an)\s+([a-z\s_]+)',
                text_lower
            )
            if inv_match:
                asserted_part = inv_match.group(1).strip()
                negated_part = inv_match.group(2).strip()
                pos_class = self._extract_class_from_text(asserted_part)
                neg_class = self._extract_class_from_text(negated_part)
                if pos_class:
                    detected_candidate_class = pos_class
                    negated_candidate_class = neg_class or current_model_class

        # 3. Direct statement search if negation pattern did not resolve
        if not detected_candidate_class:
            # Look for all matches across classes
            found_classes = []
            for cls_name, pattern in self._class_patterns.items():
                match = pattern.search(text_lower)
                if match:
                    found_classes.append((match.start(), cls_name))

            # Sort by position in text
            found_classes.sort(key=lambda x: x[0])

            if len(found_classes) == 1:
                detected_candidate_class = found_classes[0][1]
            elif len(found_classes) > 1:
                # If current_model_class is mentioned, the OTHER class is likely the intended correction
                other_classes = [c for _, c in found_classes if c != current_model_class]
                if other_classes:
                    detected_candidate_class = other_classes[-1]  # usually the stated correction
                else:
                    detected_candidate_class = found_classes[0][1]

        # 4. Handle false alarm if specifically flagged
        if is_false_alarm:
            detected_candidate_class = "false_alarm"
            correction_type = "false_alarm"
            class_id = -1
        elif detected_candidate_class:
            correction_type = "reclassify"
            class_id = self.CLASS_NAME_TO_ID.get(detected_candidate_class, 0)
        else:
            # Fallback: could not recognize an authorized class
            return {
                "valid": False,
                "error": f"Could not identify an authorized sonar class in feedback: '{input_text}'. Authorized classes are: {list(self.CLASS_REGISTRY.values())}",
                "original_class": current_model_class,
                "corrected_class": current_model_class,
                "class_id": self.CLASS_NAME_TO_ID.get(current_model_class, 0),
                "corrected_class_id": self.CLASS_NAME_TO_ID.get(current_model_class, 0),
                "correction_type": "unrecognized",
                "extracted_reason": text,
                "rationale": text
            }

        extracted_reason = self._synthesize_reason(text, current_model_class, detected_candidate_class)

        return {
            "valid": True,
            "original_class": current_model_class,
            "corrected_class": detected_candidate_class,
            "class_id": class_id,
            "corrected_class_id": class_id,
            "correction_type": correction_type,
            "confidence": 0.95,  # High human ground-truth confidence
            "extracted_reason": extracted_reason,
            "rationale": extracted_reason,
            "raw_comment": text,
            "raw_text": text
        }

    def _extract_class_from_text(self, text_segment: str) -> Optional[str]:
        """Finds if any authorized class matches the text segment."""
        for cls_name, pattern in self._class_patterns.items():
            if pattern.search(text_segment):
                return cls_name
        return None

    def _synthesize_reason(
        self,
        comment: str,
        original_class: Optional[str],
        corrected_class: str
    ) -> str:
        """Synthesizes an executive rationale string for hydrographic audit compliance."""
        clean_orig = (original_class or "unclassified").replace("_", " ")
        clean_corr = corrected_class.replace("_", " ")
        clean_comment = comment.replace("\n", " ").strip()
        if len(clean_comment) > 120:
            clean_comment = clean_comment[:117] + "..."

        if clean_orig != clean_corr:
            return f"Operator corrected from '{clean_orig}' to '{clean_corr}'. Feedback: \"{clean_comment}\""
        else:
            return f"Operator confirmed '{clean_corr}' classification. Feedback: \"{clean_comment}\""
