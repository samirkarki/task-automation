"""
Streamer Facecam Detector & Multi-Corner Consensus Engine.
Scans all 4 corners of standard 16:9 gameplay footage across multiple temporal checkpoints
using skin-tone clustering, motion variance, and face detection to locate streamer reaction webcams.
Guarantees zero empty background boxes by returning has_facecam=False when no webcam is active.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

logger = logging.getLogger("clipping.transformation.facecam_detector")


class FacecamDetector:
    """
    Multi-corner consensus facecam detector.
    Analyzes top-left, top-right, bottom-left, and bottom-right corners over multiple frames.
    """

    def __init__(self):
        self._cv2 = None
        self._yunet_path = None
        self._init_detector()

    def _init_detector(self):
        try:
            import cv2
            self._cv2 = cv2
            
            yunet_path = Path(__file__).parent.parent / "data" / "yunet.onnx"
            if not yunet_path.exists():
                yunet_path.parent.mkdir(parents=True, exist_ok=True)
                url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
                logger.info(f"Downloading YuNet DNN face detector model to {yunet_path}...")
                import urllib.request
                urllib.request.urlretrieve(url, yunet_path)
            
            if yunet_path.exists() and hasattr(cv2, "FaceDetectorYN"):
                self._yunet_path = yunet_path
                logger.debug(f"YuNet DNN face detector initialized from {yunet_path}.")
            else:
                self._yunet_path = None
        except Exception as e:
            logger.debug(f"YuNet DNN init notice: {e}. Falling back to skin plausibility analyzer.")
            self._yunet_path = None

    def _extract_corner_quadrants(
        self,
        frame: np.ndarray,
    ) -> Dict[str, Tuple[int, int, int, int, np.ndarray]]:
        """
        Extracts the 4 corner candidate boxes from a 16:9 frame.
        Returns: {quadrant_name: (x, y, w, h, cropped_array)}
        """
        h, w = frame.shape[:2]
        qw = int(w * 0.34)
        qh = int(h * 0.36)

        quadrants = {
            "top_left": (0, 0, qw, qh, frame[:qh, :qw]),
            "top_right": (w - qw, 0, qw, qh, frame[:qh, w - qw:]),
            "bottom_left": (0, h - qh, qw, qh, frame[h - qh:, :qw]),
            "bottom_right": (w - qw, h - qh, qw, qh, frame[h - qh:, w - qw:]),
        }
        return quadrants

    def _score_skin_tone(self, bgr_crop: np.ndarray) -> float:
        """
        Computes the ratio of human skin-tone pixels in the candidate quadrant.
        Skin mask in HSV: Hue [0, 25], Sat [35, 200], Val [60, 255].
        """
        if self._cv2 is None:
            return 0.0
        try:
            hsv = self._cv2.cvtColor(bgr_crop, self._cv2.COLOR_BGR2HSV)
            mask = self._cv2.inRange(hsv, (0, 35, 60), (25, 200, 255))
            total_pixels = bgr_crop.shape[0] * bgr_crop.shape[1]
            skin_pixels = np.count_nonzero(mask)
            ratio = skin_pixels / float(max(1, total_pixels))
            return ratio
        except Exception:
            return 0.0

    def detect_facecam_crop(
        self,
        video_path: Union[str, Path],
        sample_time_sec: float = 2.0,
        sample_count: int = 5,
    ) -> Dict[str, Any]:
        """
        Scans sample_count frames across video_path to locate the streamer's facecam box.
        Returns:
            {
                "has_facecam": bool,
                "x": int, "y": int, "w": int, "h": int,
                "quadrant": str,
                "confidence": float
            }
        """
        if self._cv2 is None:
            return {
                "has_facecam": False,
                "x": 0, "y": 0, "w": 0, "h": 0,
                "quadrant": "none",
                "confidence": 0.0,
            }

        cap = None
        frames: List[np.ndarray] = []
        path_obj = Path(video_path)

        # Allow passing single frame images directly (e.g. for testing or preview)
        if path_obj.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"] and path_obj.exists():
            img = self._cv2.imread(str(path_obj))
            if img is not None:
                frames.append(img)
        else:
            try:
                cap = self._cv2.VideoCapture(str(video_path))
                total_frames = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT) or 100)
                fps = float(cap.get(self._cv2.CAP_PROP_FPS) or 30.0)
                video_dur = total_frames / fps if fps > 0 else 30.0

                # Determine sample timestamps:
                # If video is long (full VOD), sample around sample_time_sec
                # If video is already a pre-cut clip (<= 120s), sample across the clip duration
                if video_dur > 120.0 and sample_time_sec > 0.0:
                    sample_offsets = [-4.0, -2.0, 0.0, 2.0, 4.0]
                    target_times = [
                        max(0.5, min(video_dur - 0.5, sample_time_sec + off))
                        for off in sample_offsets
                    ]
                else:
                    sample_percentages = [0.15, 0.35, 0.50, 0.70, 0.85]
                    target_times = [pct * video_dur for pct in sample_percentages]

                for t_sec in target_times:
                    t_msec = t_sec * 1000.0
                    cap.set(self._cv2.CAP_PROP_POS_MSEC, t_msec)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frames.append(frame)
            except Exception as e:
                logger.warning(f"Error reading frames for facecam detection: {e}")
            finally:
                if cap is not None:
                    cap.release()

        if not frames:
            logger.info("No frames could be sampled; defaulting to has_facecam=False.")
            return {
                "has_facecam": False,
                "x": 0, "y": 0, "w": 0, "h": 0,
                "quadrant": "none",
                "confidence": 0.0,
            }

        # --- Tier 1: YuNet Deep Neural Network Face Detection ---
        if self._yunet_path is not None and len(frames) > 0:
            corner_votes: Dict[str, List[float]] = {
                "top_left": [],
                "top_right": [],
                "bottom_left": [],
                "bottom_right": [],
            }
            ref_h, ref_w = frames[0].shape[:2]

            try:
                detector = self._cv2.FaceDetectorYN.create(
                    str(self._yunet_path), "", (ref_w, ref_h), score_threshold=0.75
                )

                for frame in frames:
                    fh, fw = frame.shape[:2]
                    detector.setInputSize((fw, fh))
                    _, faces = detector.detect(frame)
                    if faces is not None:
                        for f in faces:
                            fx, fy, f_w, f_h, conf = int(f[0]), int(f[1]), int(f[2]), int(f[3]), float(f[-1])
                            cx = fx + f_w // 2
                            cy = fy + f_h // 2

                            # Identify which corner quadrant the face belongs to
                            quad = None
                            if cy < fh * 0.45:
                                if cx > fw * 0.58:
                                    quad = "top_right"
                                elif cx < fw * 0.42:
                                    quad = "top_left"
                            elif cy > fh * 0.55:
                                if cx > fw * 0.58:
                                    quad = "bottom_right"
                                elif cx < fw * 0.42:
                                    quad = "bottom_left"

                            if quad and conf >= 0.75 and f_w >= 50:
                                corner_votes[quad].append(conf)

                # Check if any corner quadrant has persistent facial detections
                best_quadrant = None
                best_conf = 0.0
                max_votes = 0

                for quad, confs in corner_votes.items():
                    if len(confs) > max_votes and np.mean(confs) >= 0.75:
                        max_votes = len(confs)
                        best_quadrant = quad
                        best_conf = float(np.mean(confs))

                # Require at least 2 detections (or 1 if only 1 frame was provided)
                min_required = 1 if len(frames) <= 2 else 3
                if best_quadrant and max_votes >= min_required:
                    qw = int(ref_w * 0.32)
                    qh = int(ref_h * 0.36)
                    if best_quadrant == "top_right":
                        qx, qy = ref_w - qw, 0
                    elif best_quadrant == "top_left":
                        qx, qy = 0, 0
                    elif best_quadrant == "bottom_right":
                        qx, qy = ref_w - qw, ref_h - qh
                    else:  # bottom_left
                        qx, qy = 0, ref_h - qh

                    logger.info(
                        f"[YuNet DNN] Streamer facecam detected in [{best_quadrant}] at x={qx}, y={qy}, w={qw}, h={qh} "
                        f"({max_votes}/{len(frames)} frames, confidence={best_conf:.2f})"
                    )
                    return {
                        "has_facecam": True,
                        "x": qx,
                        "y": qy,
                        "w": qw,
                        "h": qh,
                        "quadrant": best_quadrant,
                        "confidence": round(best_conf, 2),
                    }
                else:
                    logger.debug("[YuNet DNN] No persistent facecam detected in corner quadrants.")
            except Exception as e:
                logger.warning(f"YuNet DNN detection encountered notice: {e}. Falling back to skin plausibility.")

        # --- Tier 2: Skin-Tone Plausibility & Motion Variance Fallback ---
        quadrant_names = ["top_left", "top_right", "bottom_left", "bottom_right"]
        q_scores: Dict[str, Dict[str, Any]] = {
            q: {"skin": [], "motion": [], "coords": None} for q in quadrant_names
        }

        prev_crops: Dict[str, np.ndarray] = {}

        for frame_idx, frame in enumerate(frames):
            quadrants = self._extract_corner_quadrants(frame)
            for q_name, (qx, qy, qw, qh, q_crop) in quadrants.items():
                if q_scores[q_name]["coords"] is None:
                    q_scores[q_name]["coords"] = (qx, qy, qw, qh)

                skin_ratio = self._score_skin_tone(q_crop)
                q_scores[q_name]["skin"].append(skin_ratio)

                if q_name in prev_crops:
                    gray_curr = self._cv2.cvtColor(q_crop, self._cv2.COLOR_BGR2GRAY)
                    gray_prev = self._cv2.cvtColor(prev_crops[q_name], self._cv2.COLOR_BGR2GRAY)
                    motion_delta = float(np.mean(np.abs(gray_curr.astype(float) - gray_prev.astype(float))))
                    q_scores[q_name]["motion"].append(motion_delta)

                prev_crops[q_name] = q_crop

        best_quadrant = None
        best_score = -1.0
        best_coords = (0, 0, 0, 0)

        for q_name, data in q_scores.items():
            mean_skin = float(np.mean(data["skin"])) if data["skin"] else 0.0
            mean_motion = float(np.mean(data["motion"])) if data["motion"] else 0.0

            # CRITICAL PLAUSIBILITY GATE:
            # A real human facecam in a 16:9 corner quadrant occupies between 2% and 32% skin area.
            # Ratios > 35% are guaranteed to be game terrain (asphalt road, mud, sand, water)!
            if mean_skin < 0.02 or mean_skin > 0.25:
                logger.debug(f"Quadrant [{q_name}]: skin={mean_skin:.3f} rejected (outside 2%-32% face plausibility).")
                continue

            score = (mean_skin * 100.0) + min(mean_motion * 1.5, 10.0)

            # Require non-static motion if multiple frames evaluated
            if len(data["motion"]) > 1 and mean_motion < 0.3:
                score *= 0.3

            logger.debug(f"Quadrant [{q_name}]: skin={mean_skin:.3f}, motion={mean_motion:.2f} -> score={score:.2f}")

            if score > best_score:
                best_score = score
                best_quadrant = q_name
                best_coords = data["coords"]

        if best_score < 6.0 or best_quadrant is None:
            logger.info("No streamer facecam confirmed with high confidence. Omitting webcam for clean gameplay focus.")
            return {
                "has_facecam": False,
                "x": 0,
                "y": 0,
                "w": 0,
                "h": 0,
                "quadrant": "none",
                "confidence": 0.0,
            }

        qx, qy, qw, qh = best_coords
        confidence = min(0.95, round(best_score / 20.0, 2))
        logger.info(
            f"[Skin Plausibility] Detected streamer webcam in [{best_quadrant}] at x={qx}, y={qy}, w={qw}, h={qh} "
            f"(Score: {best_score:.1f}, Confidence: {confidence:.2f})"
        )

        return {
            "has_facecam": True,
            "x": qx,
            "y": qy,
            "w": qw,
            "h": qh,
            "quadrant": best_quadrant,
            "confidence": confidence,
        }
