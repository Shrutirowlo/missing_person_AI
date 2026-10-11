import { useEffect, useState } from 'react';
import api from '../api/client';

/** Renders one ORIGINAL dataset/gallery photo (fetched with auth as a blob). */
export default function DatasetThumb({ photoId, srcUrl, label, similarity, model = 'arcface' }) {
  const [url, setUrl] = useState('');
  const [failed, setFailed] = useState(false);
  // axios already prefixes baseURL '/api' — strip a redundant '/api' from
  // server-supplied URL paths or the request becomes '/api/api/...' (404).
  const raw = srcUrl || `/dataset/photo?model=${model}&index=${photoId}`;
  const target = raw.startsWith('/api/') ? raw.slice(4) : raw;

  useEffect(() => {
    let live = true;
    let obj = '';
    api
      .get(target, { responseType: 'blob' })
      .then((res) => {
        obj = URL.createObjectURL(res.data);
        if (live) setUrl(obj);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [target]);

  if (failed) return null;
  return (
    <figure style={{ margin: 0 }}>
      {url ? <img src={url} alt={label} /> : <div className="muted" style={{ width: 120, height: 120 }}>…</div>}
      <figcaption className="muted" style={{ fontSize: '0.75rem' }}>{label} · {similarity}</figcaption>
    </figure>
  );
}
