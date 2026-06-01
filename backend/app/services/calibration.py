"""
Post-hoc temperature scaling (Guo et al., ICML 2017).

The fine-tune `Huysun29/cbt-llama-3.1-8b` may ship a
`temperature_calibration.json` fitted on a held-out set. T scaling brings
ECE into a usable range without changing the argmax / accuracy.

Format we accept (any of these — auto-detected on load):

  # 1. Single scalar
  {"temperature": 1.42}

  # 2. Per-class (e.g. per CBT technique head)
  {"temperatures": {"decatastrophizing": 1.31, "reality testing": 1.27, ...}}

  # 3. Wrapper with metadata
  {"temperature": 1.42, "ece_before": 0.733, "ece_after": 0.08,
   "fit_method": "lbfgs", "n_holdout": 514}

After T is loaded:
  calibrated_prob = softmax(logits / T)
  calibrated_confidence = max(calibrated_prob)

If the LLM endpoint only returns a confidence scalar (no logits) we
approximate via inverse-logit: logit = log(p/(1-p)); scaled = sigmoid(logit/T).
This is an approximation but works fine for surfacing a single max-class
confidence to the clinician dashboard.
"""
import json
import logging
import math
import os
from pathlib import Path
from typing import Dict, Optional, List

from huggingface_hub import hf_hub_download

from app.core.config import settings


log = logging.getLogger(__name__)


_DEFAULT_T = 1.0
_state: Dict = {
    "loaded": False,
    "temperature": _DEFAULT_T,
    "per_class": {},
    "source": None,
    "metadata": {},
}


def _download_or_local() -> Optional[Path]:
    """Try local cache first, then HF hub."""
    # 1) local mount (Docker compose maps ./models → /app/models)
    local = Path("/app/models/temperature_calibration.json")
    if local.exists():
        return local
    # 2) Hugging Face hub
    try:
        path = hf_hub_download(
            repo_id=settings.hf_model_repo,
            filename="temperature_calibration.json",
            token=os.environ.get("HF_TOKEN"),
        )
        return Path(path)
    except Exception as e:
        log.warning(
            "temperature_calibration.json: could not fetch (%s) — "
            "using T=%.2f (no calibration)", e, _DEFAULT_T)
        return None


def load_calibration() -> None:
    """Idempotent — call once at startup."""
    if _state["loaded"]:
        return
    path = _download_or_local()
    if path is None:
        _state["loaded"] = True
        return
    try:
        data = json.loads(path.read_text())
        if "temperature" in data and isinstance(data["temperature"], (int, float)):
            _state["temperature"] = float(data["temperature"])
        if "temperatures" in data and isinstance(data["temperatures"], dict):
            _state["per_class"] = {
                k.lower().strip(): float(v)
                for k, v in data["temperatures"].items()
            }
        _state["metadata"] = {
            k: v for k, v in data.items()
            if k not in ("temperature", "temperatures")
        }
        _state["source"] = str(path)
        _state["loaded"] = True
        log.info("Temperature calibration loaded from %s: T=%.3f%s",
                 path, _state["temperature"],
                 f" + {len(_state['per_class'])} per-class T"
                 if _state["per_class"] else "")
    except Exception as e:
        log.warning("Failed to parse temperature_calibration.json (%s) — "
                     "using T=%.2f", e, _DEFAULT_T)
        _state["loaded"] = True


def get_temperature(technique: Optional[str] = None) -> float:
    """Pick per-class T if available, else global T."""
    if not _state["loaded"]:
        load_calibration()
    if technique:
        key = technique.lower().strip()
        if key in _state["per_class"]:
            return _state["per_class"][key]
    return _state["temperature"]


def calibrate_probs(logits: List[float],
                     technique: Optional[str] = None) -> List[float]:
    """Apply softmax(logits/T) for a confidence distribution."""
    T = get_temperature(technique)
    if T == 0:
        T = 1.0
    scaled = [z / T for z in logits]
    m = max(scaled)
    exps = [math.exp(z - m) for z in scaled]
    s = sum(exps)
    return [e / s for e in exps]


def calibrate_confidence(raw_confidence: float,
                          technique: Optional[str] = None) -> float:
    """
    When the upstream returns a single max-class probability instead
    of full logits, approximate calibration in logit space:
        logit = log(p / (1 - p))
        cal_p = sigmoid(logit / T)
    """
    if not _state["loaded"]:
        load_calibration()
    p = max(min(raw_confidence, 0.999), 0.001)
    T = get_temperature(technique)
    if T == 0:
        T = 1.0
    logit = math.log(p / (1 - p))
    cal_logit = logit / T
    return 1.0 / (1.0 + math.exp(-cal_logit))


def status() -> Dict:
    if not _state["loaded"]:
        load_calibration()
    return {
        "loaded": _state["loaded"],
        "global_temperature": _state["temperature"],
        "per_class_count": len(_state["per_class"]),
        "source": _state["source"],
        "metadata": _state["metadata"],
    }
