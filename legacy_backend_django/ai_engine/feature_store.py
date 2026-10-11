"""
feature_store.py
Maintains fast in-memory embedding caches and handles vector synchronization with the database.
"""
import os
import json
import numpy as np

class FeatureStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FeatureStore, cls).__new__(cls)
            cls._instance.records = []
            cls._instance.is_synced = False
        return cls._instance

    def clear(self):
        """Clears cached feature records."""
        self.records = []
        self.is_synced = False

    def add_record(self, case_id, case_name, record_id, arcface_vec, cnn_vec, mediapipe_vec, metadata=None):
        """Adds or updates a single case record in the in-memory store."""
        # Convert arrays to numpy float32
        arc_arr = np.asarray(arcface_vec, dtype=np.float32) if arcface_vec is not None else None
        cnn_arr = np.asarray(cnn_vec, dtype=np.float32) if cnn_vec is not None else None
        mp_arr = np.asarray(mediapipe_vec, dtype=np.float32) if mediapipe_vec is not None else None

        # Remove existing record if present
        self.records = [r for r in self.records if r['case_id'] != case_id]

        self.records.append({
            'case_id': str(case_id),
            'case_name': str(case_name),
            'record_id': record_id,
            'arcface_vector': arc_arr,
            'cnn_vector': cnn_arr,
            'mediapipe_vector': mp_arr,
            'metadata': metadata or {},
        })

    def get_all_records(self):
        """Returns all cached target records."""
        return self.records

    def sync_from_database(self):
        """
        Queries Django Case & PersonPhoto models and refreshes in-memory vector cache.
        """
        try:
            from cases.models import MissingPerson, PersonPhoto

            photos = PersonPhoto.objects.select_related('case', 'case__reporting_station').filter(
                case__isnull=False
            )

            new_records = []
            for photo in photos:
                case = photo.case
                if not photo.arcface_vector:
                    continue

                arc_vec = np.array(json.loads(photo.arcface_vector), dtype=np.float32) if photo.arcface_vector else None
                cnn_vec = np.array(json.loads(photo.cnn_vector), dtype=np.float32) if photo.cnn_vector else None
                mp_vec = np.array(json.loads(photo.mediapipe_vector), dtype=np.float32) if photo.mediapipe_vector else None

                station_info = {
                    'name': case.reporting_station.name if case.reporting_station else 'Unknown Station',
                    'city': case.reporting_station.city if case.reporting_station else '',
                    'state': case.reporting_station.state if case.reporting_station else '',
                    'contact_phone': case.reporting_station.contact_phone if case.reporting_station else '',
                }

                new_records.append({
                    'case_id': str(case.case_id),
                    'case_name': str(case.full_name),
                    'record_id': case.id,
                    'arcface_vector': arc_vec,
                    'cnn_vector': cnn_vec,
                    'mediapipe_vector': mp_vec,
                    'metadata': {
                        'age': case.age,
                        'gender': case.gender,
                        'case_type': case.case_type,
                        'status': case.status,
                        'date_missing_or_found': str(case.date_missing_or_found) if case.date_missing_or_found else None,
                        'last_seen_location': case.last_seen_location,
                        'station': station_info,
                        'photo_url': photo.image.url if photo.image else None,
                        'crop_url': photo.face_crop.url if photo.face_crop else None,
                    }
                })

            self.records = new_records
            self.is_synced = True
            print(f"[FeatureStore] Synced {len(self.records)} case embedding records into memory.")
        except Exception as e:
            print(f"[FeatureStore] Database sync error (tables may be pending migration): {e}")
