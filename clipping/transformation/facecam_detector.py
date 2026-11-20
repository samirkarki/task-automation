"""
Streamer Facecam Detector & Smart Framing Engine.
Detects streamer facecam coordinates across standard 16:9 gameplay streams
(e.g., top-left, bottom-left, top-right, or bottom-right corner overlays)
and outputs optimal crop parameters for 9:16 split-screen rendering.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

logger = logging.getLogger("clipping.transformation.facecam_detector")


class FacecamDetector:
    """
    Detects the streamer's camera quadrant from a 16:9 video frame.
    Uses OpenCV Haar cascade when available; falls back to standard streamer quadrant presets.
    """

    # Standard streamer camera locations in 1920x1080 canvas:
    # (x_offset, y_offset, width, height)
    PRESET_QUADRANTS: Dict[str, Tuple[int, int, int, int]] = {
        "bottom_right": (1440, 680, 480, 400),
        "bottom_left": (0, 680, 480, 400),
        "top_right": (1440, 0, 480, 400),
        "top_left": (0, 0, 480, 400),
        "center_left": (0, 340, 480, 400),
    }

    def __init__(self):
        self._cv2 = None
        self._cascade = None
        self._init_detector()

    def _init_detector(self):
        try:
            import cv2
            self._cv2 = cv2
            # Load default frontal face Haar cascade
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(cascade_path)
            logger.info("OpenCV Haar cascade initialized for streamer facecam detection.")
        except Exception as e:
            logger.info(f"OpenCV face detection unavailable ({e}). Using streamer layout heuristics.")

    def detect_facecam_crop(
        self,
        video_path: Union[str, Path],
        sample_time_sec: float = 5.0,
        source_width: int = 1920,
        source_height: int = 1080,
    ) -> Dict[str, Any]:
        """
        Samples a frame from video_path at sample_time_sec to detect the streamer's facecam box.
        Returns:
            {
                "x": int, "y": int, "w": int, "h": int,
                "quadrant": str,
                "confidence": float
            }
        """
        if self._cv2 and self._cascade:
            try:
                cap = self._cv2.VideoCapture(str(video_path))
                cap.set(self._cv2.CAP_PROP_POS_MSEC, sample_time_sec * 1000.0)
                ret, frame = cap.read()
                cap.release()

                if ret and frame is not None:
                    h, w, _ = frame.shape
                    gray = self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2GRAY)
                    faces = self._cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.15,
                        minNeighbors=5,
                        minSize=(60, 60),
                        maxSize=(int(w * 0.45), int(h * 0.55)),
                    )

                    if len(faces) > 0:
                        # Sort by area (largest face in a corner is almost certainly the streamer)
                        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
                        fx, fy, fw, fh = faces[0]

                        # Expand face bbox to capture streamer shoulders and webcam frame
                        pad_w = int(fw * 0.8)
                        pad_h = int(fh * 0.9)
                        crop_x = max(0, fx - pad_w // 2)
                        crop_y = max(0, fy - int(pad_h * 0.4))
                        crop_w = min(w - crop_x, fw + pad_w)
                        crop_h = min(h - crop_y, fh + pad_h)

                        # Enforce 4:3 or ~1:1 aspect ratio for the top panel
                        target_aspect = 1080.0 / 680.0  # ~1.58
                        crop_w = int(crop_h * target_aspect)
                        if crop_x + crop_w > w:
                            crop_x = max(0, w - crop_w)

                        quadrant_name = "detected_face"
                        if crop_x < w // 3:
                            quadrant_name = "left_cam"
                        elif crop_x > (w * 2) // 3:
                            quadrant_name = "right_cam"

                        logger.info(
                            f"Detected streamer facecam at x={crop_x}, y={crop_y}, "
                            f"w={crop_w}, h={crop_h} ({quadrant_name})"
                        )
                        return {
                            "x": crop_x,
                            "y": crop_y,
                            "w": crop_w,
                            "h": crop_h,
                            "quadrant": quadrant_name,
                            "confidence": 0.92,
                        }
            except Exception as e:
                logger.warning(f"Error in OpenCV face detection ({e}). Falling back to heuristic.")

        # Fallback heuristic: Default to bottom-right or top-left standard streamer cam
        # Most GTA streamers (xQc, Kai, Speed) position webcam in bottom-right or top-left
        default_quadrant = "bottom_right"
        qx, qy, qw, qh = self.PRESET_QUADRANTS[default_quadrant]

        logger.info(f"Using default streamer quadrant: {default_quadrant} (x={qx}, y={qy})")
        return {
            "x": qx,
            "y": qy,
            "w": qw,
            "h": qh,
            "quadrant": default_quadrant,
            "confidence": 0.65,
        }
