"""
face_detector.py
Intelligent face detector and preprocessor.
Automatically distinguishes between already-cropped face photos (like LFW images)
and normal full photographs needing face detection & alignment.
"""
import os
import cv2
import numpy as np

class FaceDetector:
    def __init__(self):
        self.cascade = None
        self._init_cascade()

    def _init_cascade(self):
        try:
            cascade_cls = getattr(cv2, 'CascadeClassifier', None)
            if cascade_cls is not None:
                cascade_path = getattr(cv2.data, 'haarcascades', '') + 'haarcascade_frontalface_default.xml'
                if os.path.exists(cascade_path):
                    self.cascade = cascade_cls(cascade_path)
                else:
                    local_candidates = [
                        os.path.join(os.path.dirname(__file__), 'haarcascade_frontalface_default.xml'),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../missing_person_AI-main/mpp/src/haarcascade_frontalface_default.xml')),
                    ]
                    for cand in local_candidates:
                        if os.path.exists(cand):
                            self.cascade = cascade_cls(cand)
                            break
        except Exception:
            self.cascade = None

    def load_image(self, image_source):
        """Loads image from path, buffer, or numpy array into BGR numpy array."""
        if isinstance(image_source, np.ndarray):
            return image_source.copy()
        elif hasattr(image_source, 'read'):
            image_source.seek(0)
            file_bytes = np.frombuffer(image_source.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image from file stream")
            return img
        elif isinstance(image_source, (str, os.PathLike)):
            img = cv2.imread(str(image_source))
            if img is None:
                raise ValueError(f"Could not read image from path: {image_source}")
            return img
        elif isinstance(image_source, (bytes, bytearray)):
            file_bytes = np.frombuffer(image_source, np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Could not decode image bytes")
            return img
        else:
            raise TypeError(f"Unsupported image source type: {type(image_source)}")

    def extract_largest_face(self, image_source, target_size=None, margin=0.10):
        """
        Extracts the primary face crop.
        If the image is already a small cropped face (< 220px), returns the original image.
        Otherwise detects the face bounding box and crops with padding.
        """
        img = self.load_image(image_source)
        if img is None:
            return None, None

        h, w = img.shape[:2]

        # Small image is already a face crop (e.g., LFW database images)
        if min(h, w) < 220:
            crop = img
            bbox = (0, 0, w, h)
        else:
            faces = []
            if self.cascade is not None:
                try:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.equalizeHist(gray)
                    faces = self.cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(50, 50),
                        flags=getattr(cv2, 'CASCADE_SCALE_IMAGE', 2)
                    )
                except Exception:
                    faces = []

            if len(faces) > 0:
                # Pick largest detected face
                largest = max(faces, key=lambda f: f[2] * f[3])
                x, y, fw, fh = largest
                pad_x = int(fw * margin)
                pad_y = int(fh * margin)

                x1 = max(0, x - pad_x)
                y1 = max(0, y - pad_y)
                x2 = min(w, x + fw + pad_x)
                y2 = min(h, y + fh + pad_y)

                crop = img[y1:y2, x1:x2]
                bbox = (int(x), int(y), int(fw), int(fh))
            else:
                crop = img
                bbox = (0, 0, w, h)

        if target_size is not None and crop is not None and crop.size > 0:
            crop = cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)

        return crop, bbox
