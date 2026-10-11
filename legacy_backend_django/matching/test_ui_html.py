"""
test_ui.html
Interactive Browser-based AI Match Tester for Missing Person AI Backend.
Allows uploading any query photo and visualizing side-by-side ArcFace, CNN, and MediaPipe comparative results + top 10 candidates.
"""
TEST_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Missing Person AI - 3-Model Comparative Face Search Tester</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0b0f19;
            --bg-secondary: #111827;
            --bg-card: rgba(17, 24, 39, 0.75);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-muted: #9ca3af;
            --accent-arc: #6366f1;
            --accent-cnn: #ec4899;
            --accent-mp: #10b981;
            --accent-cyan: #06b6d4;
            --badge-match: #10b981;
            --badge-possible: #f59e0b;
            --badge-nomatch: #ef4444;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, var(--bg-primary) 70%);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem 1rem;
        }

        .container {
            max-width: 1280px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            margin-bottom: 2.5rem;
        }

        .badge-header {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 1rem;
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 9999px;
            color: #818cf8;
            font-size: 0.85rem;
            font-weight: 600;
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        h1 {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 50%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .subtitle {
            color: var(--text-muted);
            font-size: 1.05rem;
            max-width: 600px;
            margin: 0 auto;
        }

        .grid-layout {
            display: grid;
            grid-template-columns: 380px 1fr;
            gap: 2rem;
            align-items: start;
        }

        @media (max-width: 960px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }

        .glass-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 1.75rem;
            backdrop-filter: blur(16px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        }

        .card-title {
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* Upload Area */
        .upload-dropzone {
            border: 2px dashed rgba(255, 255, 255, 0.15);
            border-radius: 1rem;
            padding: 2rem 1.5rem;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
            background: rgba(255, 255, 255, 0.02);
            position: relative;
        }

        .upload-dropzone:hover, .upload-dropzone.dragover {
            border-color: var(--accent-arc);
            background: rgba(99, 102, 241, 0.05);
        }

        .upload-icon {
            font-size: 2.5rem;
            margin-bottom: 0.75rem;
        }

        .preview-box {
            margin-top: 1rem;
            display: none;
            text-align: center;
        }

        .preview-img {
            max-width: 100%;
            max-height: 240px;
            border-radius: 0.75rem;
            object-fit: cover;
            border: 2px solid var(--border-color);
        }

        .file-info {
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
        }

        /* Model selectors */
        .model-toggles {
            margin: 1.5rem 0;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }

        .toggle-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
        }

        .toggle-label {
            font-size: 0.95rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        .dot-arc { background: var(--accent-arc); box-shadow: 0 0 10px var(--accent-arc); }
        .dot-cnn { background: var(--accent-cnn); box-shadow: 0 0 10px var(--accent-cnn); }
        .dot-mp  { background: var(--accent-mp);  box-shadow: 0 0 10px var(--accent-mp); }

        .btn-search {
            width: 100%;
            padding: 1rem;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            border: none;
            border-radius: 0.75rem;
            color: #ffffff;
            font-weight: 700;
            font-size: 1.05rem;
            cursor: pointer;
            box-shadow: 0 10px 25px rgba(99, 102, 241, 0.35);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .btn-search:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 30px rgba(99, 102, 241, 0.5);
        }

        .btn-search:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        /* Results Area */
        .verdict-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.25rem 1.75rem;
            border-radius: 1rem;
            margin-bottom: 1.5rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-color);
        }

        .verdict-badge {
            padding: 0.5rem 1.25rem;
            border-radius: 9999px;
            font-weight: 800;
            font-size: 0.95rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }

        .verdict-MATCH { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }
        .verdict-POSSIBLE { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
        .verdict-NO { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }

        /* Comparative Cards */
        .models-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }

        @media (max-width: 640px) {
            .models-grid { grid-template-columns: 1fr; }
        }

        .model-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.25rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .model-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 3px;
        }
        .model-card.arc::before { background: var(--accent-arc); }
        .model-card.cnn::before { background: var(--accent-cnn); }
        .model-card.mp::before { background: var(--accent-mp); }

        .model-name {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }

        .model-score {
            font-size: 2.25rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .model-status {
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.6rem;
            border-radius: 9999px;
            display: inline-block;
        }

        .status-HIGH { background: rgba(16, 185, 129, 0.15); color: #34d399; }
        .status-MODERATE { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
        .status-LOW { background: rgba(239, 68, 68, 0.15); color: #f87171; }

        /* Candidates Table */
        .table-wrap {
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }

        th {
            padding: 0.85rem 1rem;
            color: var(--text-muted);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }

        td {
            padding: 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            vertical-align: middle;
        }

        tr:hover {
            background: rgba(255, 255, 255, 0.02);
        }

        .candidate-user {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .thumb-img {
            width: 44px;
            height: 44px;
            border-radius: 0.5rem;
            object-fit: cover;
            border: 1px solid var(--border-color);
            background: #1f2937;
        }

        .score-pill {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
        }

        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 0.8s ease-in-out infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        .empty-state {
            text-align: center;
            padding: 4rem 1rem;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="badge-header">⚡ Missing Person AI Live Verification Suite</div>
            <h1>Comparative Face Recognition Engine</h1>
            <p class="subtitle">Upload any query photograph to search across registered police stations and NGOs using <strong>ArcFace</strong>, <strong>CNN</strong>, and <strong>MediaPipe</strong> concurrently.</p>
        </header>

        <div class="grid-layout">
            <!-- Left: Upload & Controls -->
            <div class="glass-card">
                <div class="card-title">📷 Upload Query Photograph</div>

                <div class="upload-dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
                    <div class="upload-icon">📤</div>
                    <div style="font-weight: 600; margin-bottom: 0.25rem;">Click or drag photo here</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">Supports JPG, PNG, WEBP</div>
                    <input type="file" id="fileInput" accept="image/*" style="display: none;" onchange="handleFileSelect(event)">
                </div>

                <div class="preview-box" id="previewBox">
                    <img id="previewImg" class="preview-img" alt="Query Preview">
                    <div class="file-info" id="fileInfo"></div>
                </div>

                <div class="model-toggles">
                    <div class="toggle-item">
                        <span class="toggle-label"><span class="dot dot-arc"></span> ArcFace Buffalo_L (512-D)</span>
                        <span style="font-size: 0.8rem; color: #818cf8; font-weight: 600;">ACTIVE</span>
                    </div>
                    <div class="toggle-item">
                        <span class="toggle-label"><span class="dot dot-cnn"></span> Deep CNN Feature Model (128-D)</span>
                        <span style="font-size: 0.8rem; color: #f472b6; font-weight: 600;">ACTIVE</span>
                    </div>
                    <div class="toggle-item">
                        <span class="toggle-label"><span class="dot dot-mp"></span> MediaPipe 3D Mesh (478-pt)</span>
                        <span style="font-size: 0.8rem; color: #34d399; font-weight: 600;">ACTIVE</span>
                    </div>
                </div>

                <button class="btn-search" id="searchBtn" onclick="runSearch()" disabled>
                    <span>⚡ Search & Compare Database</span>
                </button>
            </div>

            <!-- Right: Results Matrix & Top 10 -->
            <div class="glass-card" id="resultsCard">
                <div class="card-title">📊 Comparative Verification Matrix</div>

                <div id="emptyResults" class="empty-state">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">🔍</div>
                    <div style="font-size: 1.1rem; font-weight: 600; color: #e5e7eb;">No search executed yet</div>
                    <div style="font-size: 0.9rem; margin-top: 0.25rem;">Select an image on the left and click "Search & Compare" to view side-by-side AI scores.</div>
                </div>

                <div id="resultsContent" style="display: none;">
                    <div class="verdict-banner">
                        <div>
                            <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase;">Consensus Match Verdict</div>
                            <div id="verdictText" style="font-size: 1.3rem; font-weight: 800; margin-top: 0.2rem;">MATCH FOUND</div>
                            <div id="latencyText" style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.2rem;">Inference time: 1480 ms</div>
                        </div>
                        <div id="verdictBadge" class="verdict-badge verdict-MATCH">92.4% Consensus</div>
                    </div>

                    <div class="models-grid">
                        <div class="model-card arc">
                            <div class="model-name">ArcFace Buffalo_L</div>
                            <div class="model-score" id="arcScore" style="color: #818cf8;">--%</div>
                            <div class="model-status status-HIGH" id="arcStatus">HIGH CONFIDENCE</div>
                        </div>
                        <div class="model-card cnn">
                            <div class="model-name">Deep Face CNN</div>
                            <div class="model-score" id="cnnScore" style="color: #f472b6;">--%</div>
                            <div class="model-status status-MODERATE" id="cnnStatus">MODERATE</div>
                        </div>
                        <div class="model-card mp">
                            <div class="model-name">MediaPipe 3D Mesh</div>
                            <div class="model-score" id="mpScore" style="color: #34d399;">--%</div>
                            <div class="model-status status-HIGH" id="mpStatus">HIGH CONFIDENCE</div>
                        </div>
                    </div>

                    <div style="font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;">
                        <span>🏆 Top 10 Candidate Identities in Database</span>
                        <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 400;">Ranked by AI Consensus</span>
                    </div>

                    <div class="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Rank</th>
                                    <th>Candidate Name</th>
                                    <th>Branch / Station</th>
                                    <th>ArcFace</th>
                                    <th>CNN</th>
                                    <th>MediaPipe</th>
                                    <th>Consensus</th>
                                </tr>
                            </thead>
                            <tbody id="candidateTableBody">
                                <!-- Populated dynamically -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let selectedFile = null;

        function handleFileSelect(e) {
            const file = e.target.files[0];
            if (file) loadFile(file);
        }

        const dropzone = document.getElementById('dropzone');
        dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length) loadFile(e.dataTransfer.files[0]);
        });

        function loadFile(file) {
            selectedFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById('previewImg').src = e.target.result;
                document.getElementById('previewBox').style.display = 'block';
                document.getElementById('fileInfo').textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
                document.getElementById('searchBtn').disabled = false;
            };
            reader.readAsDataURL(file);
        }

        async function runSearch() {
            if (!selectedFile) return;

            const btn = document.getElementById('searchBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> <span>Running ArcFace, CNN, MediaPipe...</span>';

            const formData = new FormData();
            formData.append('image', selectedFile);

            try {
                const response = await fetch('/api/match/search/', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                renderResults(data);
            } catch (err) {
                alert('Error executing search: ' + err);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡ Search & Compare Database</span>';
            }
        }

        function renderResults(data) {
            document.getElementById('emptyResults').style.display = 'none';
            document.getElementById('resultsContent').style.display = 'block';

            const verdict = data.verdict || 'NO MATCH';
            const consensus = data.consensus_confidence || 0.0;
            const latency = data.execution_time_ms || 0;

            document.getElementById('verdictText').textContent = verdict;
            document.getElementById('latencyText').textContent = `Inference time: ${latency} ms across 3 models`;

            const badge = document.getElementById('verdictBadge');
            badge.textContent = `${consensus}% Consensus`;
            badge.className = 'verdict-badge ' + (verdict.includes('MATCH FOUND') ? 'verdict-MATCH' : (verdict.includes('POSSIBLE') ? 'verdict-POSSIBLE' : 'verdict-NO'));

            const bk = data.comparative_breakdown || {};
            const arc = bk.arcface || {};
            const cnn = bk.cnn || {};
            const mp = bk.mediapipe || {};

            document.getElementById('arcScore').textContent = `${arc.score_percentage || 0}%`;
            document.getElementById('arcStatus').textContent = (arc.status || 'N/A').replace('_', ' ');
            document.getElementById('arcStatus').className = 'model-status ' + ((arc.score_percentage >= 80) ? 'status-HIGH' : (arc.score_percentage >= 50 ? 'status-MODERATE' : 'status-LOW'));

            document.getElementById('cnnScore').textContent = `${cnn.score_percentage || 0}%`;
            document.getElementById('cnnStatus').textContent = (cnn.status || 'N/A').replace('_', ' ');
            document.getElementById('cnnStatus').className = 'model-status ' + ((cnn.score_percentage >= 70) ? 'status-HIGH' : (cnn.score_percentage >= 40 ? 'status-MODERATE' : 'status-LOW'));

            document.getElementById('mpScore').textContent = `${mp.score_percentage || 0}%`;
            document.getElementById('mpStatus').textContent = (mp.status || 'N/A').replace('_', ' ');
            document.getElementById('mpStatus').className = 'model-status ' + ((mp.score_percentage >= 70) ? 'status-HIGH' : (mp.score_percentage >= 40 ? 'status-MODERATE' : 'status-LOW'));

            const tbody = document.getElementById('candidateTableBody');
            tbody.innerHTML = '';

            const candidates = data.candidate_matches || [];
            if (candidates.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">No candidates found</td></tr>';
                return;
            }

            candidates.forEach((cand, idx) => {
                const s = cand.scores || {};
                const meta = cand.metadata || {};
                const st = meta.station || {};
                const photoUrl = meta.crop_url || meta.photo_url || '';

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td style="font-weight: 700; color: var(--text-muted);">#${idx + 1}</td>
                    <td>
                        <div class="candidate-user">
                            ${photoUrl ? `<img src="${photoUrl}" class="thumb-img" alt="${cand.name}">` : '<div class="thumb-img"></div>'}
                            <div>
                                <div style="font-weight: 700;">${cand.name}</div>
                                <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${cand.case_id}</div>
                            </div>
                        </div>
                    </td>
                    <td>
                        <div>${st.name || 'Unknown'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${st.city || ''} ${st.state || ''}</div>
                    </td>
                    <td class="score-pill" style="color: #818cf8;">${s.arcface_pct}%</td>
                    <td class="score-pill" style="color: #f472b6;">${s.cnn_pct}%</td>
                    <td class="score-pill" style="color: #34d399;">${s.mediapipe_pct}%</td>
                    <td class="score-pill" style="color: #38bdf8; font-weight: 800;">${s.consensus_pct}%</td>
                `;
                tbody.appendChild(row);
            });
        }
    </script>
</body>
</html>
"""
