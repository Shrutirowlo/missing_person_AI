"""
comparative_matcher.py
Orchestrates ArcFace, CNN, and MediaPipe face recognition engines to produce
a side-by-side comparative match matrix and consensus verdict for any query photo.
"""
import os
import cv2
import numpy as np
from .face_detector import FaceDetector
from .arcface_engine import ArcFaceEngine
from .cnn_engine import CNNEngine
from .mediapipe_engine import MediaPipeEngine

class ComparativeMatcher:
    def __init__(self):
        self.detector = FaceDetector()
        self.arcface = ArcFaceEngine()
        self.cnn = CNNEngine()
        self.mediapipe = MediaPipeEngine()

    def process_query_image(self, image_source):
        """
        Loads image, detects face, crops face, and extracts all 3 feature vectors.
        Returns dict containing original image, face crop, bbox, and feature vectors.
        """
        img = self.detector.load_image(image_source)
        if img is None:
            raise ValueError("Could not decode or load the provided query image.")

        face_crop, bbox = self.detector.extract_largest_face(img)

        # Extract features from the face crop
        arc_emb = self.arcface.extract_embedding(face_crop)
        cnn_emb = self.cnn.extract_embedding(face_crop)
        mp_feat = self.mediapipe.extract_features(face_crop)

        return {
            'image_bgr': img,
            'face_crop_bgr': face_crop,
            'bbox': bbox,
            'arcface_vector': arc_emb,
            'cnn_vector': cnn_emb,
            'mediapipe_vector': mp_feat,
        }

    def compare(self, query_data, target_records, models=('arcface', 'cnn', 'mediapipe')):
        """
        Compares extracted query features against a list of target database records.
        target_records format:
        [
            {
                'case_id': '...',
                'case_name': '...',
                'record_id': 1,
                'arcface_vector': np.ndarray,
                'cnn_vector': np.ndarray,
                'mediapipe_vector': np.ndarray,
                'metadata': {...}
            },
            ...
        ]
        models: subset of ('arcface', 'cnn', 'mediapipe') to evaluate.
        All raw similarity values come from the existing engines; this method
        only normalizes presentation and ranking. No ensemble retraining.

        Returns a detailed comparative analysis dictionary.
        """
        # Normalize / validate requested models (orchestration only, AI untouched)
        valid = ('arcface', 'cnn', 'mediapipe')
        if models is None:
            models = valid
        if isinstance(models, str):
            models = (models,)
        requested = tuple(m for m in models if m in valid) or valid
        use_arc = 'arcface' in requested
        use_cnn = 'cnn' in requested
        use_mp = 'mediapipe' in requested

        def _consensus(*pcts):
            vals = [p for p in pcts if p is not None]
            if not vals:
                return 0.0
            return round(sum(vals) / len(vals), 2)

        if not target_records:
            empty_breakdown = {}
            if use_arc:
                empty_breakdown['arcface'] = {'model_name': 'ArcFace (Buffalo_L)', 'score_percentage': 0.0, 'status': 'NO_DATA'}
            if use_cnn:
                empty_breakdown['cnn'] = {'model_name': 'Deep Face CNN', 'score_percentage': 0.0, 'status': 'NO_DATA'}
            if use_mp:
                empty_breakdown['mediapipe'] = {'model_name': 'MediaPipe Facial Mesh', 'score_percentage': 0.0, 'status': 'NO_DATA'}
            return {
                'status': 'NO_RECORDS_IN_DATABASE',
                'verdict': 'NO MATCH FOUND (DATABASE EMPTY)',
                'consensus_confidence': 0.0,
                'models_evaluated': list(requested),
                'comparative_breakdown': empty_breakdown,
                'candidate_matches': [],
            }

        q_arc = query_data.get('arcface_vector')
        q_cnn = query_data.get('cnn_vector')
        q_mp = query_data.get('mediapipe_vector')

        # 1. Run ArcFace Comparisons
        arc_targets = [r['arcface_vector'] for r in target_records if r.get('arcface_vector') is not None]
        arc_sims = self.arcface.compute_similarity(q_arc, arc_targets) if q_arc is not None and len(arc_targets) > 0 else np.zeros(len(target_records))

        # 2. Run CNN Comparisons
        cnn_targets = [r['cnn_vector'] for r in target_records if r.get('cnn_vector') is not None]
        cnn_sims = self.cnn.compute_similarity(q_cnn, cnn_targets) if q_cnn is not None and len(cnn_targets) > 0 else np.zeros(len(target_records))

        # 3. Run MediaPipe Comparisons
        mp_targets = [r['mediapipe_vector'] for r in target_records if r.get('mediapipe_vector') is not None]
        mp_sims = self.mediapipe.compute_similarity(q_mp, mp_targets) if q_mp is not None and len(mp_targets) > 0 else np.zeros(len(target_records))

        # Group by unique identity (case_id) taking the highest consensus score per individual
        unique_candidates = {}
        for i, rec in enumerate(target_records):
            arc_s = float(arc_sims[i]) if i < len(arc_sims) else 0.0
            cnn_s = float(cnn_sims[i]) if i < len(cnn_sims) else 0.0
            mp_s = float(mp_sims[i]) if i < len(mp_sims) else 0.0

            arc_pct = self.arcface.similarity_to_confidence(arc_s)
            cnn_pct = self.cnn.similarity_to_confidence(cnn_s)
            mp_pct = self.mediapipe.similarity_to_confidence(mp_s)

            active_pcts = [
                p for flag, p in
                ((use_arc, arc_pct), (use_cnn, cnn_pct), (use_mp, mp_pct))
                if flag
            ]
            consensus_pct = _consensus(*active_pcts)

            meta = rec.get('metadata', {})
            scores = {
                'consensus_pct': consensus_pct,
            }
            if use_arc:
                scores['arcface_sim'] = round(arc_s, 4)
                scores['arcface_pct'] = arc_pct
            if use_cnn:
                scores['cnn_sim'] = round(cnn_s, 4)
                scores['cnn_pct'] = cnn_pct
            if use_mp:
                scores['mediapipe_sim'] = round(mp_s, 4)
                scores['mediapipe_pct'] = mp_pct
            cand_obj = {
                'case_id': rec.get('case_id'),
                'case_db_id': rec.get('record_id'),
                'name': rec.get('case_name'),
                'full_name': rec.get('case_name'),
                'record_id': rec.get('record_id'),
                'primary_photo_url': meta.get('photo_url'),
                'face_crop_url': meta.get('crop_url'),
                'age': meta.get('age'),
                'gender': meta.get('gender'),
                'status': meta.get('status'),
                'reporting_station_name': meta.get('station', {}).get('name'),
                'contact_phone': meta.get('station', {}).get('contact_phone'),
                'metadata': meta,
                'scores': scores,
            }


            cid = rec.get('case_id')
            if cid not in unique_candidates or consensus_pct > unique_candidates[cid]['scores']['consensus_pct']:
                unique_candidates[cid] = cand_obj

        candidate_scores = list(unique_candidates.values())

        # Sort candidates by consensus score descending
        candidate_scores.sort(key=lambda c: c['scores']['consensus_pct'], reverse=True)
        top_match = candidate_scores[0] if candidate_scores else None

        # Build Comparative Breakdown for the top candidate
        if top_match:
            top_arc = top_match['scores'].get('arcface_pct', 0.0)
            top_cnn = top_match['scores'].get('cnn_pct', 0.0)
            top_mp = top_match['scores'].get('mediapipe_pct', 0.0)
            top_consensus = top_match['scores'].get('consensus_pct', 0.0)

            # Determine match verdict (uses only evaluated models; AI thresholds untouched)
            if (use_arc and top_arc >= 85.0) or top_consensus >= 75.0:
                verdict = "MATCH FOUND"
                confidence_tier = "HIGH"
            elif (use_arc and top_arc >= 60.0) or top_consensus >= 50.0:
                verdict = "POSSIBLE MATCH"
                confidence_tier = "MODERATE"
            else:
                verdict = "NO RELIABLE MATCH"
                confidence_tier = "LOW"

            def get_status(pct):
                if pct >= 80: return "HIGH_CONFIDENCE"
                if pct >= 50: return "MODERATE_CONFIDENCE"
                return "LOW_CONFIDENCE"

            breakdown = {}
            if use_arc:
                breakdown['arcface'] = {
                    'model_name': 'ArcFace Buffalo_L (Deep Angular Margin)',
                    'score_percentage': top_arc,
                    'raw_similarity': top_match['scores'].get('arcface_sim'),
                    'predicted_person': top_match['name'],
                    'status': get_status(top_arc),
                }
            if use_cnn:
                breakdown['cnn'] = {
                    'model_name': 'Deep Face CNN (Convolutional Feature Extractor)',
                    'score_percentage': top_cnn,
                    'raw_similarity': top_match['scores'].get('cnn_sim'),
                    'predicted_person': top_match['name'],
                    'status': get_status(top_cnn),
                }
            if use_mp:
                breakdown['mediapipe'] = {
                    'model_name': 'MediaPipe Facial Mesh (478-Point 3D Geometry)',
                    'score_percentage': top_mp,
                    'raw_similarity': top_match['scores'].get('mediapipe_sim'),
                    'predicted_person': top_match['name'],
                    'status': get_status(top_mp),
                }
        else:
            verdict = "NO MATCH FOUND"
            confidence_tier = "NONE"
            top_consensus = 0.0
            breakdown = {}

        return {
            'status': 'SUCCESS',
            'verdict': verdict,
            'confidence_tier': confidence_tier,
            'consensus_confidence': top_consensus,
            'models_evaluated': list(requested),
            'comparative_breakdown': breakdown,
            'candidate_matches': candidate_scores[:10],  # Return top 10 ranked candidates
        }
