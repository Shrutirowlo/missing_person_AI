"""Recognition orchestration: query image -> ORIGINAL AI -> person lookup.

No ensemble algorithm is invented. For `all`, each ORIGINAL approach runs
independently and its own result is returned. Unavailable models yield an
explicit per-model error (never a substituted result).
"""
import asyncio
import logging
import os
import time

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..ai import gallery, registry
from ..ai.result import AIMissingDependency
from ..repositories.persons import PersonRepository
from ..repositories.registered import RegisteredRepository
from ..repositories.searches import SearchRepository
from .report_matching import match_reports

logger = logging.getLogger(__name__)

MODELS = ("cnn", "arcface", "mediapipe_knn")


class RecognitionService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.persons = PersonRepository(db)
        self.searches = SearchRepository(db)
        self.adapters = {
            "cnn": registry.get_cnn(),
            "arcface": registry.get_arcface(),
            "mediapipe_knn": registry.get_mediapipe_knn(),
        }

    def availability(self) -> dict:
        return {name: adapter.status() for name, adapter in self.adapters.items()}

    def _standardize(self, model: str, raw: dict, person: dict | None,
                       matched_via: str | None, matched_photo: dict | None,
                       reg_doc: dict | None) -> dict:
        label = raw.get("predicted_label")
        gallery_identity, gallery_reason = gallery.registered_match(label)
        reg_id = reg_doc["id"] if reg_doc else None
        gallery_count = gallery.image_count(gallery_identity) if gallery_identity else 0
        sample = gallery.sample_photo(gallery_identity) if gallery_identity else None
        gallery_url = (f"/api/dataset/gallery/{gallery_identity}/{sample}"
                       if gallery_identity and sample else None)
        gallery_path = f"{gallery_identity}/{sample}" if gallery_identity and sample else None
        base_detail = {"matched_via": matched_via,
                       "matched_person_name": person["full_name"] if person else None,
                       "matched_photo_url": (f"/storage/{matched_photo['path']}"
                                             if matched_photo else None),
                       "predicted_gallery_identity": gallery_identity,
                       "gallery_reason": gallery_reason,
                       "gallery_image_count": gallery_count,
                       "gallery_image_url": gallery_url,
                       # Real folder photos of the predicted identity for
                       # visual comparison (NOT ranked matches — the original
                       # CNN index has no per-row file provenance).
                       "gallery_identity_photos": gallery.identity_photos(gallery_identity)}
        model_names = {"cnn": "CNN", "arcface": "ArcFace", "mediapipe_knn": "MediaPipe + KNN"}
        mname = model_names.get(model, model)
        if model == "cnn":
            accepted = raw.get("status") == "PREDICTED"
            match = accepted and reg_doc is not None
            # Extension-index rows (API-added photos) know their source file:
            # resolve those to real thumbnails. Original training rows have
            # no file provenance and stay text-only (nothing invented).
            top_images = []
            for t in raw.get("top_images", []):
                entry = dict(t)
                if t.get("source"):
                    url = gallery.gallery_url_for_path(t["source"])
                    if url:
                        entry["photo_url"] = url
                top_images.append(entry)
            if match:
                explanation = (
                    f"{mname} predicted '{label}' (similarity "
                    f"{raw.get('best_similarity')}, confidence "
                    f"{(raw.get('confidence') or 0) * 100:.2f}%). Gallery identity "
                    f"'{gallery_identity}' validated against {gallery_count} registered "
                    f"photos; registered record {reg_id}.")
            elif not accepted:
                explanation = f"{mname} produced no prediction — no reliable match."
            elif gallery_identity is None:
                explanation = f"{mname} predicted '{label}'. {gallery_reason}."
            else:
                explanation = (
                    f"{mname} predicted '{label}'. Identity '{gallery_identity}' exists "
                    f"in data/registered/ ({gallery_count} photos) but has not been "
                    f"imported into MongoDB — no registered record linked. Run the dataset import.")
            return {"model": model, "available": True, "match_found": match,
                    "predicted_label": label,
                    "registered_match": gallery_identity if match else None,
                    "registered_person_id": reg_id if match else None,
                    "source_photo_url": gallery_url if match else None,
                    "source_photo_path": gallery_path if match else None,
                    "person_id": person["id"] if person else None,
                    "similarity": raw.get("best_similarity"),
                    "confidence": raw.get("confidence"),
                    "status": "potential_match" if match else "no_reliable_match",
                    "explanation": explanation,
                    "detail": {**base_detail,
                               "best_class_similarity": raw.get("best_class_similarity"),
                               "top_classes": raw.get("top_classes", []),
                               "top_images": top_images}}
        if model == "arcface":
            decision = raw.get("status")
            if decision == "NO_FACE_DETECTED":
                return {"model": model, "available": True, "match_found": False,
                        "predicted_label": None, "registered_match": None,
                        "registered_person_id": None,
                        "source_photo_url": None, "source_photo_path": None,
                        "person_id": None, "similarity": None, "confidence": None,
                        "status": "no_reliable_match",
                        "explanation": (
                            f"{mname} detected no face in the query image — "
                            f"no reliable match."),
                        "detail": {**base_detail, "decision": decision,
                                   "input_type": raw.get("input_type"),
                                   "top_classes": [], "top_matches": []}}
            accepted = decision in ("MATCH_FOUND", "POSSIBLE_MATCH")
            match = accepted and reg_doc is not None
            # For ArcFace, if top match has a specific source photo from paths.npy, prioritize it
            af_photo_url = gallery_url
            af_photo_path = gallery_path
            top_matches = raw.get("top_matches", [])
            if top_matches and "source" in top_matches[0]:
                src_full = top_matches[0]["source"]
                src_filename = os.path.basename(src_full)
                if gallery_identity:
                    af_photo_url = f"/api/dataset/gallery/{gallery_identity}/{src_filename}"
                    af_photo_path = f"{gallery_identity}/{src_filename}"

            if match:
                explanation = (
                    f"{mname} decision {decision} for '{label}' (similarity "
                    f"{raw.get('similarity')}). Gallery identity '{gallery_identity}' "
                    f"validated against {gallery_count} registered photos; registered "
                    f"record {reg_id}.")
            elif not accepted:
                explanation = (
                    f"{mname} decision {decision} for '{label}' (similarity "
                    f"{raw.get('similarity')}) — below the model's acceptance threshold, "
                    f"no reliable match.")
            elif gallery_identity is None:
                explanation = f"{mname} predicted '{label}'. {gallery_reason}."
            else:
                explanation = (
                    f"{mname} predicted '{label}'. Identity '{gallery_identity}' exists "
                    f"in data/registered/ ({gallery_count} photos) but has not been "
                    f"imported into MongoDB — no registered record linked. Run the dataset import.")
            return {"model": model, "available": True, "match_found": match,
                    "predicted_label": label,
                    "registered_match": gallery_identity if match else None,
                    "registered_person_id": reg_id if match else None,
                    "source_photo_url": af_photo_url if match else None,
                    "source_photo_path": af_photo_path if match else None,
                    "person_id": person["id"] if person else None,
                    "similarity": raw.get("similarity"),
                    "confidence": None,
                    "status": ("potential_match" if match else "no_reliable_match"),
                    "explanation": explanation,
                    "detail": {**base_detail, "decision": decision, "margin": raw.get("margin"),
                               "input_type": raw.get("input_type"),
                               "top_classes": raw.get("top_classes", []),
                               "top_matches": top_matches}}
        # mediapipe_knn shape (original pipeline now integrated)
        if raw.get("status") == "NO_FACE_DETECTED":
            return {"model": model, "available": True, "match_found": False,
                    "predicted_label": None, "registered_match": None,
                    "registered_person_id": None,
                    "source_photo_url": None, "source_photo_path": None,
                    "person_id": None, "similarity": None, "confidence": None,
                    "status": "no_reliable_match",
                    "explanation": (
                        f"{mname} detected no face in the query image — "
                        f"no reliable match."),
                    "detail": {**base_detail, "decision": "NO_FACE_DETECTED",
                               "top_classes": [], "top_matches": []}}
        match = reg_doc is not None
        # If the top neighbour has a specific source photo from the ORIGINAL
        # paths.npy, prioritize it (same behaviour as the ArcFace branch).
        mp_photo_url = gallery_url
        mp_photo_path = gallery_path
        top_matches = raw.get("top_matches", [])
        if top_matches and "source" in top_matches[0] and gallery_identity:
            src_filename = os.path.basename(top_matches[0]["source"])
            mp_photo_url = f"/api/dataset/gallery/{gallery_identity}/{src_filename}"
            mp_photo_path = f"{gallery_identity}/{src_filename}"
        if match:
            explanation = (
                f"{mname} predicted '{label}'. Gallery identity '{gallery_identity}' "
                f"validated against {gallery_count} registered photos; registered "
                f"record {reg_id}.")
        elif gallery_identity is None:
            explanation = f"{mname} predicted '{label}'. {gallery_reason or 'no prediction'}."
        else:
            explanation = (
                f"{mname} predicted '{label}'. Identity '{gallery_identity}' exists "
                f"in data/registered/ but has not been imported into MongoDB — "
                f"run the dataset import.")
        return {"model": model, "available": True, "match_found": match,
                "predicted_label": label,
                "registered_match": gallery_identity if match else None,
                "registered_person_id": reg_id if match else None,
                "source_photo_url": mp_photo_url if match else None,
                "source_photo_path": mp_photo_path if match else None,
                "person_id": person["id"] if person else None,
                "similarity": raw.get("similarity"), "confidence": raw.get("confidence"),
                "status": "potential_match" if match else "no_reliable_match",
                "explanation": explanation,
                "detail": {**base_detail, **raw}}

    async def _run_one(self, model: str, image_bytes: bytes) -> dict:
        """Run one model, fully isolated, with per-model timing.

        Any failure — model runtime, image decoding, or the database lookup
        — becomes THAT model's error card; it never affects the other models
        or fails the request as a whole."""
        started = time.perf_counter()
        try:
            payload = await self._run_one_inner(model, image_bytes)
        except AIMissingDependency as exc:
            payload = {"model": model, "available": False, "match_found": False,
                       "predicted_label": None, "registered_match": None,
                       "registered_person_id": None,
                       "source_photo_url": None, "source_photo_path": None,
                       "person_id": None, "similarity": None,
                       "confidence": None, "status": "model_unavailable", "detail": {},
                       "explanation": str(exc),
                       "error": str(exc)}
        except ValueError as exc:
            # Undecodable/corrupt query image: the model's own verdict is
            # invalid input — reported per-model, never failing the request.
            payload = {"model": model, "available": True, "match_found": False,
                       "predicted_label": None, "registered_match": None,
                       "registered_person_id": None,
                       "source_photo_url": None, "source_photo_path": None,
                       "person_id": None, "similarity": None,
                       "confidence": None, "status": "invalid_image", "detail": {},
                       "explanation": str(exc),
                       "error": str(exc)}
        except Exception as exc:  # undecodable/corrupt image, runtime or DB failure
            payload = {"model": model, "available": True, "match_found": False,
                       "predicted_label": None, "registered_match": None,
                       "registered_person_id": None,
                       "source_photo_url": None, "source_photo_path": None,
                       "person_id": None, "similarity": None,
                       "confidence": None, "status": "error", "detail": {},
                       "explanation": str(exc),
                       "error": str(exc)}
        detail = payload.get("detail")
        if isinstance(detail, dict):
            detail["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return payload

    async def _run_one_inner(self, model: str, image_bytes: bytes) -> dict:
        adapter = self.adapters[model]
        raw = await asyncio.to_thread(adapter.recognize, image_bytes)
        person, matched_photo, matched_via = None, None, None
        if raw.get("predicted_label"):
            # 1. reference photo tagged by the SAME original model, 2. name fallback.
            person, matched_photo = await self.persons.find_by_photo_label(
                model, raw["predicted_label"])
            matched_via = "reference_photo" if person else None
            if person is None:
                person = await self.persons.find_by_name(raw["predicted_label"])
                matched_via = "name" if person else None
        reg_doc = None
        gallery_identity, _reason = gallery.registered_match(raw.get("predicted_label"))
        if gallery_identity:
            reg_doc = await RegisteredRepository(self.db).get_by_identity(gallery_identity)
        return self._standardize(model, raw, person, matched_via, matched_photo, reg_doc)

    def _summarize(self, results: dict[str, dict]) -> dict:
        """Combined verdict over per-model results.

        Pure orchestration: it only compares the models' own outcomes and
        never invents scores or forces agreement. verdict is one of
        "consistent" (every running model that produced a reliable match
        agrees on the same identity), "conflicting" (models disagree —
        different identities, or some matched while others did not), or
        "inconclusive" (no model produced a reliable registered match).
        """
        model_names = {"cnn": "CNN", "arcface": "ArcFace", "mediapipe_knn": "MediaPipe + KNN"}
        matched = [r for r in results.values()
                   if r.get("available") and r.get("match_found") and r.get("registered_match")]
        errored = [r for r in results.values()
                   if r.get("available") and r.get("error")]
        no_match = [r for r in results.values()
                    if r.get("available") and not r.get("match_found") and not r.get("error")]
        unavailable = [r for r in results.values() if not r.get("available")]
        identities = sorted({r["registered_match"] for r in matched})

        if len(identities) > 1:
            verdict = "conflicting"
            named = ", ".join(f"{model_names.get(r['model'], r['model'])} → {r['registered_match']}"
                              for r in matched)
            message = f"Models disagree on the identity: {named}."
        elif identities and no_match:
            verdict = "conflicting"
            named = ", ".join(model_names.get(r["model"], r["model"]) for r in matched)
            rest = ", ".join(model_names.get(r["model"], r["model"]) for r in no_match)
            message = (f"{named} produced a reliable match, but {rest} did not — "
                       f"conflicting evidence.")
        elif identities:
            verdict = "consistent"
            who = ", ".join(model_names.get(r["model"], r["model"]) for r in matched)
            message = (f"Models that produced a reliable match agree on "
                       f"'{identities[0]}' ({who}).")
        elif unavailable and not no_match and not errored:
            verdict = "inconclusive"
            message = "No model could run, so no comparison is possible."
        else:
            verdict = "inconclusive"
            message = "No model produced a reliable registered match for this image."

        if unavailable:
            who = ", ".join(model_names.get(r["model"], r["model"]) for r in unavailable)
            message += f" Unavailable (not run): {who}."
        if errored:
            who = ", ".join(model_names.get(r["model"], r["model"]) for r in errored)
            message += f" Errored (see the model's card for the real error): {who}."
        return {
            "verdict": verdict,
            "matched_identities": identities,
            "models_with_match": [r["model"] for r in matched],
            "models_without_match": [r["model"] for r in no_match],
            "models_unavailable": [r["model"] for r in unavailable],
            "models_errored": [r["model"] for r in errored],
            "message": message,
        }

    async def recognize(self, image_bytes: bytes, model: str, user_id: str,
                        query_url: str | None = None) -> dict:
        selected = list(MODELS) if model == "all" else [model]
        search = await self.searches.create_search(
            {"searched_by": user_id, "model": model, "query_image_url": query_url}
        )
        # Run the models CONCURRENTLY: each is an independent CPU-bound
        # runtime with its own inference lock, so they overlap instead of
        # serializing, and one model's failure never blocks the others
        # (_run_one is fully guarded).
        started = time.perf_counter()
        payloads = await asyncio.gather(
            *(self._run_one(name, image_bytes) for name in selected))
        results = {}
        for name, payload in zip(selected, payloads):
            results[name] = payload
            await self.searches.add_result(search["id"], name, payload)
        total_ms = round((time.perf_counter() - started) * 1000, 1)
        summary = self._summarize(results)
        summary["timings"] = {
            name: (results[name].get("detail") or {}).get("elapsed_ms")
            for name in selected
        }
        summary["total_elapsed_ms"] = total_ms
        logger.info("recognition search_id=%s models=%s total=%.0fms timings=%s",
                    search["id"], ",".join(selected), total_ms, summary["timings"])
        # Staff-only field-report match: nearest stored report photo by
        # original-pipeline embedding (CNN/ArcFace). Never blocks or alters
        # the per-model verdicts above; failures simply yield no match.
        report_match = None
        try:
            report_match = await match_reports(self.db, image_bytes)
        except Exception as exc:
            logger.warning("recognition search_id=%s report matching skipped: %s",
                           search["id"], exc)
        if report_match is not None:
            summary["report_match"] = report_match
            await self.searches.set_report_match(search["id"], report_match)
            logger.info("recognition search_id=%s report_match person=%s sim=%s via=%s",
                        search["id"], report_match.get("person_name"),
                        report_match.get("similarity"), report_match.get("model"))
        search_id = search["id"]
        return {"search_id": search_id, "models_evaluated": selected,
                "results": results, "query_image_url": query_url,
                "summary": summary, "report_match": report_match}
