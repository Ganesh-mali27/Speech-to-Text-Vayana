// Attach to the global window so script.js can call toggleLiveRecording when hitting "Back to Home"
window.isLive = false;

let mediaRecorder;
let liveAudioSocket;
let liveIntervalId;
let currentStream = null;
const liveIntervalMs = 15000; // 15 seconds chunk

const liveBtn = document.getElementById('start-live-btn');
const liveStatusContainer = document.getElementById('live-status-container');
const liveStatus = document.getElementById('live-status-text');
const chunksContainer = document.getElementById('live-chunks-container');
const btnLiveReport = document.getElementById('btn-live-report');

let allLiveIntentData = [];

// Connect WebSocket
function connectLiveSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    liveAudioSocket = new WebSocket(`${protocol}//${window.location.host}/api/live/ws`);

    liveAudioSocket.onopen = () => {
        console.log("Live WebSocket Connected!");
    };

    liveAudioSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Live Socket Data:", data);

        if (data.error) {
            console.error("Live Error:", data.error);
            return;
        }

        if (data.status === 'processing') {
            liveStatus.textContent = data.message;
        } else if (data.status === 'completed') {
            liveStatus.textContent = "Waiting for next chunk...";
            // Update UI dynamically with the chunk results
            appendLiveChunk(data);
        }
    };

    liveAudioSocket.onclose = () => {
        console.log("Live WebSocket Disconnected");
    };
}

// Helper function to create a completely fresh recording chunk
function startNewChunk() {
    if (!currentStream) return;

    mediaRecorder = new MediaRecorder(currentStream, { mimeType: 'audio/webm' });

    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && liveAudioSocket.readyState === WebSocket.OPEN) {
            console.log(`Sending chunk of size: ${event.data.size}`);
            liveAudioSocket.send(event.data);
        }
    };

    mediaRecorder.start();
}

// Start/Stop Live Recording
window.toggleLiveRecording = async function () {
    if (window.isLive) {
        // Stop
        if (liveIntervalId) {
            clearInterval(liveIntervalId);
        }
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
        }
        if (currentStream) {
            currentStream.getTracks().forEach(track => track.stop());
        }
        window.isLive = false;

        liveBtn.innerHTML = '<i class="ph ph-microphone"></i> Start Live Call';
        liveBtn.classList.remove('btn-danger');
        liveBtn.classList.add('btn-accent');
        liveBtn.classList.add('pulse-btn');

        liveStatusContainer.style.display = 'none';

    } else {
        // Start
        try {
            if (!liveAudioSocket || liveAudioSocket.readyState !== WebSocket.OPEN) {
                connectLiveSocket();
            }

            currentStream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Clear previous chunks and report data
            chunksContainer.innerHTML = '';
            allLiveIntentData = [];
            btnLiveReport.style.display = 'inline-flex';

            // Start the first chunk
            startNewChunk();

            // Restart recording every 15 seconds with a brand new MediaRecorder instance
            liveIntervalId = setInterval(() => {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    mediaRecorder.stop(); // Finish previous chunk
                    startNewChunk();      // Create fresh WebM file for next chunk
                }
            }, liveIntervalMs);

            window.isLive = true;
            liveBtn.innerHTML = '<i class="ph ph-stop-circle"></i> Stop Live Call';
            liveBtn.classList.remove('btn-accent');
            liveBtn.classList.remove('pulse-btn');
            liveBtn.classList.add('btn-danger');

            liveStatus.textContent = "Recording... Sending chunks every 15s.";
            liveStatusContainer.style.display = 'block';

        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Could not access microphone. Please allow permissions.");
        }
    }
};

let chunkCounterUI = 1;

function appendLiveChunk(data) {
    const chunkId = data.chunk_id;
    const transcriptData = data.transcript_data;
    const intentData = data.intent_data;

    // Accumulate intent data for report
    if (intentData && intentData.length > 0) {
        allLiveIntentData = allLiveIntentData.concat(intentData);
    }

    // Create Accordion Container
    const accordionItem = document.createElement('div');
    accordionItem.className = 'accordion-item glass-card mb-4';

    // Format Current Time
    const now = new Date();
    const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // Header
    const header = document.createElement('div');
    header.className = 'accordion-header';
    header.innerHTML = `
        <div class="chunk-info">
            <i class="ph ph-waveform"></i>
            <span>Chunk ${chunkCounterUI++}</span>
            <span class="chunk-time">${timeString}</span>
        </div>
        <i class="ph ph-caret-down accordion-icon"></i>
    `;

    // Body
    const body = document.createElement('div');
    body.className = 'accordion-body';

    // 1. Audio Player for the chunk
    const audioContainer = document.createElement('div');
    audioContainer.className = 'chunk-audio';
    audioContainer.innerHTML = `
        <h4 class="mb-2" style="font-size: 0.95rem; color: var(--text-secondary);"><i class="ph ph-speaker-hifi"></i> Audio</h4>
        <audio controls src="/api/live/audio/${chunkId}"></audio>
    `;

    // 2. Grid for Transcript & Intent
    const grid = document.createElement('div');
    grid.className = 'chunk-content-grid';

    // Transcript Build
    let transcriptHtml = '';
    if (transcriptData && transcriptData.length > 0) {
        transcriptData.forEach(segment => {
            transcriptHtml += `
                <div class="mb-2">
                    <span class="speaker-badge" style="font-size: 0.75rem; padding: 0.15rem 0.4rem; margin-right: 0.5rem;"><i class="ph ph-user"></i> ${segment.speaker}</span>
                    <span style="font-size: 0.95rem;">${segment.transliterated_text || segment.text}</span>
                </div>`;
        });
    } else {
        transcriptHtml = '<p class="text-secondary">No speech detected.</p>';
    }

    const transcriptSection = document.createElement('div');
    transcriptSection.className = 'chunk-transcript';
    transcriptSection.innerHTML = `
        <h4 class="mb-2" style="font-size: 0.95rem; color: var(--text-secondary);"><i class="ph ph-text-align-left"></i> Transcript</h4>
        ${transcriptHtml}
    `;

    // Intent Table Build
    let tableRows = '';
    if (intentData && intentData.length > 0) {
        intentData.forEach(segment => {
            let flaggedHtml = '';
            if (segment.flagged_keywords && segment.flagged_keywords.length > 0) {
                flaggedHtml = segment.flagged_keywords.map(kw => `<span class="badge danger">${kw}</span>`).join(' ');
            } else {
                flaggedHtml = `<span class="badge neutral">None</span>`;
            }

            let intentHtml = segment.intent || 'Neutral';
            if (intentHtml !== 'Neutral') {
                intentHtml = `<span class="badge intent">${intentHtml}</span>`;
            }

            const riskScore = segment.risk_score || 0;
            const riskClass = riskScore > 50 ? 'risk-high' : 'risk-low';

            tableRows += `
                <tr>
                    <td><span class="speaker-badge" style="font-size: 0.75rem; padding: 0.15rem 0.4rem;"><i class="ph ph-user"></i> ${segment.speaker}</span></td>
                    <td>${flaggedHtml}</td>
                    <td>${intentHtml}</td>
                    <td><span class="${riskClass}">${riskScore}%</span></td>
                </tr>
            `;
        });
    } else {
        tableRows = '<tr><td colspan="4" class="text-center text-secondary" style="font-size: 0.85rem;">No intent data</td></tr>';
    }

    const intentSection = document.createElement('div');
    intentSection.className = 'table-responsive';
    intentSection.innerHTML = `
        <h4 class="mb-2" style="font-size: 0.95rem; color: var(--text-secondary);"><i class="ph ph-shield-warning"></i> Analysis</h4>
        <table style="font-size: 0.85rem;">
            <thead>
                <tr>
                    <th>Speaker</th>
                    <th>Keywords</th>
                    <th>Intent</th>
                    <th>Risk</th>
                </tr>
            </thead>
            <tbody>
                ${tableRows}
            </tbody>
        </table>
    `;

    // Assemble
    grid.appendChild(transcriptSection);
    grid.appendChild(intentSection);

    body.appendChild(audioContainer);
    body.appendChild(grid);

    accordionItem.appendChild(header);
    accordionItem.appendChild(body);

    // Accordion Toggle Logic
    header.addEventListener('click', () => {
        accordionItem.classList.toggle('open');
    });

    // By default, open the newest chunk
    accordionItem.classList.add('open');

    // Prepend to show newest at top (or append to show at bottom)
    chunksContainer.prepend(accordionItem);
}

if (liveBtn) {
    liveBtn.addEventListener('click', window.toggleLiveRecording);
}

if (btnLiveReport) {
    btnLiveReport.addEventListener('click', () => {
        if (window.showReport) {
            window.showReport(allLiveIntentData);
        }
    });
}
