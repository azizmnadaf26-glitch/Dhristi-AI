"""DEMO / STUB ENGINE. Returns deterministic fake results, NOT real model output.

The real MATLAB adapter will replace this and must return the same dictionary shape.
"""

ENGINE_MODE = "demo_stub"


DEMO_METRICS = {
    "dimensions": "1024 x 1024",
    "width": 1024,
    "height": 1024,
    "mean_brightness": 0.3330,
    "contrast_std": 0.1837,
    "sharpness_score": 0.0162,
    "retinal_area_ratio": 78.77,
    "dimensions_pass": True,
    "brightness_pass": True,
    "contrast_pass": True,
    "sharpness_pass": True,
    "retinal_area_pass": True,
    "overall_status": "Preliminary checks passed",
    "field_detected": True,
    "field_status": "Preliminary field detected",
    "field_message": "A sufficiently large non-dark region was detected.",
}

UNUSABLE_METRICS = {
    "dimensions": "1024 x 1024",
    "width": 1024,
    "height": 1024,
    "mean_brightness": 0.0420,
    "contrast_std": 0.0210,
    "sharpness_score": 0.0008,
    "retinal_area_ratio": 12.40,
    "dimensions_pass": True,
    "brightness_pass": False,
    "contrast_pass": False,
    "sharpness_pass": False,
    "retinal_area_pass": False,
    "overall_status": "Review required",
    "field_detected": False,
    "field_status": "Review required",
    "field_message": "Retinal field boundary or sharpness check failed.",
}


def analyze_image(sha256_hex: str) -> dict:
    n = int(sha256_hex[:8], 16)

    if n % 5 == 0:
        return {
            "schema_version": "screening-1.0",
            "engine_mode": ENGINE_MODE,
            "quality": {
                "verdict": "unusable",
                "reason_codes": ["blurry"],
                "metrics": UNUSABLE_METRICS,
            },
            "prediction": None,
        }

    grade = (n // 5) % 5
    raw = [0.05] * 5
    raw[grade] = 0.6 + ((n // 25) % 30) / 100
    total = sum(raw)
    scores = [round(v / total, 3) for v in raw]
    return {
        "schema_version": "screening-1.0",
        "engine_mode": ENGINE_MODE,
        "quality": {
            "verdict": "usable",
            "reason_codes": [],
            "metrics": DEMO_METRICS,
        },
        "prediction": {"grade": grade, "class_scores": scores, "model_score": max(scores)},
    }