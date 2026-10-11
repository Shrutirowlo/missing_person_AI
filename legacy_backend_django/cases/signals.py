import os
import json
import cv2
import numpy as np
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.files.base import ContentFile
from .models import PersonPhoto

_detector = None
_arcface = None
_cnn = None
_mediapipe = None
_feature_store = None

def get_ai_services():
    global _detector, _arcface, _cnn, _mediapipe, _feature_store
    if _detector is None:
        from ai_engine.face_detector import FaceDetector
        from ai_engine.arcface_engine import ArcFaceEngine
        from ai_engine.cnn_engine import CNNEngine
        from ai_engine.mediapipe_engine import MediaPipeEngine
        from ai_engine.feature_store import FeatureStore
        _detector = FaceDetector()
        _arcface = ArcFaceEngine()
        _cnn = CNNEngine()
        _mediapipe = MediaPipeEngine()
        _feature_store = FeatureStore()
    return _detector, _arcface, _cnn, _mediapipe, _feature_store

@receiver(post_save, sender=PersonPhoto)
def process_photo_and_extract_embeddings(sender, instance, created, **kwargs):
    """
    Automatically detects face, generates crop, extracts ArcFace, CNN, and MediaPipe vectors,
    and updates the in-memory FeatureStore.
    """
    if not instance.image:
        return

    # Only process if vectors are not already populated
    if not instance.arcface_vector or not instance.face_crop:
        try:
            detector, arcface, cnn, mediapipe, feature_store = get_ai_services()
            image_path = instance.image.path
            img = cv2.imread(image_path)
            if img is None:
                return

            face_crop, bbox = detector.extract_largest_face(img)
            if face_crop is None:
                face_crop = img
                bbox = (0, 0, img.shape[1], img.shape[0])

            # Extract vectors
            arc_vec = arcface.extract_embedding(face_crop)
            cnn_vec = cnn.extract_embedding(face_crop)
            mp_vec = mediapipe.extract_features(face_crop)

            # Save face crop image
            is_success, buffer = cv2.imencode(".jpg", face_crop)
            if is_success:
                crop_filename = f"crop_{os.path.basename(instance.image.name)}"
                instance.face_crop.save(crop_filename, ContentFile(buffer.tobytes()), save=False)

            instance.bounding_box = json.dumps(list(bbox))
            instance.arcface_vector = json.dumps(arc_vec.tolist() if arc_vec is not None else [])
            instance.cnn_vector = json.dumps(cnn_vec.tolist() if cnn_vec is not None else [])
            instance.mediapipe_vector = json.dumps(mp_vec.tolist() if mp_vec is not None else [])
            
            # Save without triggering infinite signal recursion
            PersonPhoto.objects.filter(pk=instance.pk).update(
                bounding_box=instance.bounding_box,
                arcface_vector=instance.arcface_vector,
                cnn_vector=instance.cnn_vector,
                mediapipe_vector=instance.mediapipe_vector,
                face_crop=instance.face_crop.name
            )
        except Exception as e:
            print(f"[Signals] Error processing photo #{instance.id}: {e}")

    # Update in-memory FeatureStore
    try:
        _, _, _, _, feature_store = get_ai_services()
        case = instance.case
        arc_arr = json.loads(instance.arcface_vector) if instance.arcface_vector else None
        cnn_arr = json.loads(instance.cnn_vector) if instance.cnn_vector else None
        mp_arr = json.loads(instance.mediapipe_vector) if instance.mediapipe_vector else None

        station_info = {
            'name': case.reporting_station.name if case.reporting_station else 'Unknown Station',
            'city': case.reporting_station.city if case.reporting_station else '',
            'state': case.reporting_station.state if case.reporting_station else '',
            'contact_phone': case.reporting_station.contact_phone if case.reporting_station else '',
        }

        feature_store.add_record(
            case_id=case.case_id,
            case_name=case.full_name,
            record_id=case.id,
            arcface_vec=arc_arr,
            cnn_vec=cnn_arr,
            mediapipe_vec=mp_arr,
            metadata={
                'age': case.age,
                'gender': case.gender,
                'case_type': case.case_type,
                'status': case.status,
                'date_missing_or_found': str(case.date_missing_or_found) if case.date_missing_or_found else None,
                'last_seen_location': case.last_seen_location,
                'station': station_info,
                'photo_url': instance.image.url if instance.image else None,
                'crop_url': instance.face_crop.url if instance.face_crop else None,
            }
        )
    except Exception as e:
        print(f"[Signals] FeatureStore add error: {e}")

@receiver(post_delete, sender=PersonPhoto)
def on_photo_deleted(sender, instance, **kwargs):
    try:
        _, _, _, _, feature_store = get_ai_services()
        feature_store.sync_from_database()
    except Exception:
        pass
