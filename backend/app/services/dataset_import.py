"""Idempotent import of data/registered/ into MongoDB (read-only on disk).

For every identity folder under the ORIGINAL registered dataset, this
creates/updates:
  - registered_persons: one document per identity (keyed by identity)
  - registered_images:  one document per photograph (keyed by rel path)

Only directory listings + file sizes are read; image binaries are never
loaded and the original files are never moved, renamed, or modified.
Re-running the import creates no duplicates (unique keys + upserts) and
never touches users, missing_persons, or search history. A summary is
recorded in import_runs.
"""
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from ..ai import gallery


def _now():
    return datetime.now(timezone.utc)


async def import_registered_dataset(db: AsyncIOMotorDatabase,
                                    dataset_root: str | None = None) -> dict:
    root = dataset_root or gallery.gallery_dir()
    report: dict = {
        "dataset_root": root,
        "started_at": _now().isoformat(),
        "identities_found": 0,
        "persons_created": 0,
        "persons_matched": 0,
        "images_found": 0,
        "images_created": 0,
        "images_matched": 0,
        "skipped_files": [],
        "errors": [],
    }
    try:
        folders = sorted(
            e for e in os.listdir(root) if os.path.isdir(os.path.join(root, e))
        )
    except OSError as exc:
        report["errors"].append(f"cannot list dataset root {root}: {exc}")
        report["finished_at"] = _now().isoformat()
        return report
    report["identities_found"] = len(folders)

    persons = db["registered_persons"]
    images = db["registered_images"]

    for identity in folders:
        folder = os.path.join(root, identity)
        try:
            names = sorted(os.listdir(folder))
        except OSError as exc:
            report["errors"].append(f"cannot list {identity}: {exc}")
            continue
        valid = [
            n for n in names
            if os.path.isfile(os.path.join(folder, n))
            and os.path.splitext(n)[1].lower() in gallery.SUPPORTED_PHOTO_EXTS
        ]
        skipped = [n for n in names if n not in valid]
        for n in skipped:
            full = os.path.join(folder, n)
            if os.path.isdir(full):
                report["skipped_files"].append(f"{identity}/{n} (not a file)")
            else:
                report["skipped_files"].append(f"{identity}/{n} (unsupported type)")
        report["images_found"] += len(valid)

        sample_file = valid[0] if valid else None
        res = await persons.update_one(
            {"identity": identity},
            {"$set": {"identity": identity,
                       "name": identity.replace("_", " ").title(),
                       "source_folder": identity,
                       "dataset_root": root,
                       "image_count": len(valid),
                       "sample_image": sample_file,
                       "sample_image_path": f"{identity}/{sample_file}" if sample_file else None,
                       "sample_image_url": f"/api/dataset/gallery/{identity}/{sample_file}" if sample_file else None,
                       "updated_at": _now()},
             "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )
        if res.upserted_id is not None:
            report["persons_created"] += 1
            person_id = res.upserted_id
        else:
            report["persons_matched"] += 1
            doc = await persons.find_one({"identity": identity}, {"_id": 1})
            person_id = doc["_id"]

        for name in valid:
            rel_path = f"{identity}/{name}"
            try:
                size = os.path.getsize(os.path.join(folder, name))
            except OSError as exc:
                report["errors"].append(f"cannot stat {rel_path}: {exc}")
                continue
            ires = await images.update_one(
                {"rel_path": rel_path},
                {"$set": {"rel_path": rel_path,
                          "identity": identity,
                          "filename": name,
                          "extension": os.path.splitext(name)[1].lower(),
                          "size_bytes": size,
                          "registered_person_id": person_id,
                          "url": f"/api/dataset/gallery/{identity}/{name}",
                          "updated_at": _now()},
                 "$setOnInsert": {"created_at": _now()}},
                upsert=True,
            )
            if ires.upserted_id is not None:
                report["images_created"] += 1
            else:
                report["images_matched"] += 1

    report["finished_at"] = _now().isoformat()
    await db["import_runs"].insert_one(
        {"kind": "registered_dataset", **{k: v for k, v in report.items()}}
    )
    return report
