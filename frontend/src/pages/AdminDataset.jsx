import { useState } from 'react';
import api, { errMsg } from '../api/client';

export default function AdminDataset() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const runImport = async () => {
    if (!window.confirm('Run the dataset import? This is an additive-only operation.')) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const res = await api.post('/dataset/import');
      setResult(res.data);
    } catch (err) {
      setError(errMsg(err, 'Import failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>Dataset Management</h1>
      <div className="card">
        <h3>Import Registered-Person Dataset</h3>
        <p className="muted">
          Import or re-sync the registered-person data from the original dataset directory.
          This operation is additive-only and will not delete existing records.
        </p>
        {error && <div className="error">{error}</div>}
        {result && (
          <div className="success">
            Import complete — {result.persons_matched ?? 0} persons
            ({result.persons_created ?? 0} new)
            , {result.images_matched ?? 0} images
            ({result.images_created ?? 0} new).
          </div>
        )}
        <button className="btn btn-primary" disabled={busy} onClick={runImport}>
          {busy ? 'Importing…' : 'Run Import'}
        </button>
      </div>
    </div>
  );
}
