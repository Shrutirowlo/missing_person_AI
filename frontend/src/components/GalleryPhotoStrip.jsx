import DatasetThumb from './DatasetThumb';

/** Thumbnail strip of real gallery photos.
 *  items: [{url, label, similarity}]. Used for CNN top matches that resolve
 *  to a file AND for the predicted identity's folder photos. Purely visual
 *  comparison — ranking honesty is documented in each title. */
export default function GalleryPhotoStrip({ title, note, items }) {
  const photos = (items || []).filter((t) => t?.url);
  if (!photos.length) return null;
  return (
    <details open>
      <summary>{title}</summary>
      <div className="thumbs">
        {photos.slice(0, 10).map((t, i) => (
          <DatasetThumb key={`${t.url}-${i}`} srcUrl={t.url} label={t.label} similarity={t.similarity} />
        ))}
      </div>
      {note && <p className="muted">{note}</p>}
    </details>
  );
}
