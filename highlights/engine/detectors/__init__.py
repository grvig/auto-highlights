"""Per-type highlight detectors.

Each module here defines one Detector: it reads a DetectionContext and returns
Moments of a single HighlightType for the chosen player. Detectors never import
each other — the clip-plan builder is what composes them.
"""
