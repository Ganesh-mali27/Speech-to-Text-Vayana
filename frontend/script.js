// DOM Elements
const homeView = document.getElementById('home-view');
const uploadView = document.getElementById('upload-view');
const liveView = document.getElementById('live-view');
const backHomeBtn = document.getElementById('back-home-btn');

const cardUpload = document.getElementById('card-upload');
const cardLive = document.getElementById('card-live');

// Upload View Elements
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const selectedFileDiv = document.getElementById('selected-file');
const fileNameSpan = document.getElementById('file-name');
const uploadBtn = document.getElementById('upload-btn');
const uploadSection = document.getElementById('upload-section');
const statusSection = document.getElementById('status-section');
const uploadResults = document.getElementById('upload-results');
const statusText = document.getElementById('status-text');
const statusMessage = document.getElementById('status-message');
const audioPlayer = document.getElementById('audio-player');
const intentTableBody = document.querySelector('#intent-table tbody');
const transcriptContent = document.getElementById('transcript-content');

// Report Modal Elements
const reportModal = document.getElementById('report-modal');
const btnCloseReport = document.getElementById('btn-close-report');
const btnDownloadPdf = document.getElementById('btn-download-pdf');
const btnUploadReport = document.getElementById('btn-upload-report');
const reportSpeakerBreakdown = document.getElementById('report-speaker-breakdown');

let currentFile = null;
let currentIntentData = null;

// ===================== NAVIGATION LOGIC =====================
function showView(view) {
    homeView.classList.remove('active');
    uploadView.classList.remove('active');
    liveView.classList.remove('active');

    // Small delay for animation
    setTimeout(() => {
        homeView.style.display = 'none';
        uploadView.style.display = 'none';
        liveView.style.display = 'none';
        
        view.style.display = 'block';
        setTimeout(() => view.classList.add('active'), 10);
        
        if (view === homeView) {
            backHomeBtn.style.display = 'none';
        } else {
            backHomeBtn.style.display = 'inline-flex';
        }
    }, 300);
}

cardUpload.addEventListener('click', () => showView(uploadView));
cardLive.addEventListener('click', () => showView(liveView));

backHomeBtn.addEventListener('click', () => {
    // Stop live recording if it's active
    if (typeof window.isLive !== 'undefined' && window.isLive) {
        window.toggleLiveRecording();
    }
    
    // Reset Upload State
    uploadSection.style.display = 'block';
    statusSection.style.display = 'none';
    uploadResults.style.display = 'none';
    currentFile = null;
    selectedFileDiv.style.display = 'none';
    
    showView(homeView);
});


// ===================== UPLOAD LOGIC =====================
uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleFileSelect(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileSelect(e.target.files[0]);
    }
});

function handleFileSelect(file) {
    currentFile = file;
    fileNameSpan.textContent = file.name;
    selectedFileDiv.style.display = 'flex';
}

uploadBtn.addEventListener('click', async () => {
    if (!currentFile) return;

    const formData = new FormData();
    formData.append('file', currentFile);

    uploadSection.style.display = 'none';
    statusSection.style.display = 'block';
    statusText.textContent = 'Processing Audio...';
    statusText.style.color = 'var(--text-primary)';

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Upload failed');
        
        const data = await response.json();
        pollStatus(data.task_id);
    } catch (error) {
        statusText.textContent = 'Error';
        statusMessage.textContent = error.message;
        statusText.style.color = 'var(--danger)';
        document.querySelector('.spinner').style.display = 'none';
    }
});

function pollStatus(taskId) {
    document.querySelector('.spinner').style.display = 'block';
    
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${taskId}`);
            const data = await response.json();

            if (data.status === 'processing') {
                statusMessage.textContent = data.message;
            } else if (data.status === 'completed') {
                clearInterval(interval);
                displayResults(data);
            } else if (data.status === 'failed') {
                clearInterval(interval);
                statusText.textContent = 'Processing Failed';
                statusMessage.textContent = data.message;
                statusText.style.color = 'var(--danger)';
                document.querySelector('.spinner').style.display = 'none';
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}

function displayResults(data) {
    statusSection.style.display = 'none';
    uploadResults.style.display = 'block';

    // Set audio source
    audioPlayer.src = `/api/audio/${data.audio_filename}`;

    // Clear previous data
    intentTableBody.innerHTML = '';
    transcriptContent.innerHTML = '';

    // Populate Data
    if(data.intent_data && data.intent_data.length > 0) {
        currentIntentData = data.intent_data;
        data.intent_data.forEach(segment => {
            // 1. Populate Transcript
            const transcriptDiv = document.createElement('div');
            transcriptDiv.className = 'transcript-segment';
            transcriptDiv.innerHTML = `
                <div class="speaker"><i class="ph ph-user"></i> ${segment.speaker}</div>
                <div class="text">${segment.transliterated_text}</div>
            `;
            transcriptContent.appendChild(transcriptDiv);

            // 2. Populate Intent Table
            const tr = document.createElement('tr');
            
            const keywordsHTML = segment.flagged_keywords.length > 0 
                ? segment.flagged_keywords.map(k => `<span class="badge danger">${k}</span>`).join('') 
                : '<span class="badge neutral">None</span>';
                
            const intentsHTML = segment.intent_detected.length > 0
                ? segment.intent_detected.map(i => `<span class="badge intent">${i}</span>`).join('')
                : '<span class="badge neutral">Neutral</span>';

            const riskLevel = segment.risk_confidence.level === 'high' ? 'risk-high' : 'risk-low';

            tr.innerHTML = `
                <td><span class="speaker-badge"><i class="ph ph-user"></i> ${segment.speaker}</span></td>
                <td>${keywordsHTML}</td>
                <td>${intentsHTML}</td>
                <td class="${riskLevel}">${segment.risk_confidence.percentage}</td>
            `;
            intentTableBody.appendChild(tr);
        });
    } else {
        transcriptContent.innerHTML = '<p class="text-secondary p-4">No speech detected.</p>';
        intentTableBody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary">No data available</td></tr>';
        currentIntentData = null;
    }
}

// ===================== REPORT GENERATION LOGIC =====================

// Attach global function so live_script.js can use it too
window.showReport = function(intentData) {
    if (!intentData || intentData.length === 0) {
        alert("No data available to generate report.");
        return;
    }

    const speakerMap = {};
    let totalHighRisk = 0;
    let totalLowRisk = 0;

    intentData.forEach(segment => {
        const spk = segment.speaker || 'Unknown';
        if (!speakerMap[spk]) {
            speakerMap[spk] = { high: 0, low: 0, intents: new Set() };
        }

        const isHighRisk = (segment.risk_confidence && segment.risk_confidence.level === 'high') || (segment.risk_score && segment.risk_score > 50);

        if (isHighRisk) {
            speakerMap[spk].high++;
            totalHighRisk++;
        } else {
            speakerMap[spk].low++;
            totalLowRisk++;
        }

        let currentIntents = [];
        if (segment.intent_detected && Array.isArray(segment.intent_detected)) {
            currentIntents = segment.intent_detected;
        } else if (segment.intent) {
            currentIntents = [segment.intent];
        }

        currentIntents.forEach(i => {
            if (i !== 'Neutral') speakerMap[spk].intents.add(i);
        });
    });

    // Populate Top Summary
    document.getElementById('rep-total-speakers').textContent = Object.keys(speakerMap).length;
    document.getElementById('rep-high-risk').textContent = totalHighRisk;
    document.getElementById('rep-low-risk').textContent = totalLowRisk;
    document.getElementById('report-date').textContent = new Date().toLocaleString();

    // Populate Speaker Breakdown
    let breakdownHtml = '';
    for (const [speaker, stats] of Object.entries(speakerMap)) {
        let intentPills = Array.from(stats.intents).map(i => `<span class="intent-pill">${i}</span>`).join('');
        if (!intentPills) intentPills = '<span class="intent-pill" style="background:#f3f4f6; color:#6b7280; border-color:#e5e7eb;">Neutral/None</span>';

        breakdownHtml += `
            <div class="speaker-report-item">
                <div class="speaker-report-header">
                    <div class="speaker-report-name"><i class="ph ph-user"></i> ${speaker}</div>
                </div>
                <div class="speaker-stats-grid">
                    <div class="stat-box high-risk">
                        <h5>${stats.high}</h5>
                        <p>High Risk Alerts</p>
                    </div>
                    <div class="stat-box low-risk">
                        <h5>${stats.low}</h5>
                        <p>Low Risk Segments</p>
                    </div>
                </div>
                <div>
                    <h5 style="font-size: 0.9rem; color: #374151; margin-bottom: 0.5rem; text-transform: uppercase;">Key Intents Detected</h5>
                    <div class="intent-pills">
                        ${intentPills}
                    </div>
                </div>
            </div>
        `;
    }

    reportSpeakerBreakdown.innerHTML = breakdownHtml;

    // Show Modal
    reportModal.style.display = 'flex';
};

btnUploadReport.addEventListener('click', () => {
    if (currentIntentData) {
        window.showReport(currentIntentData);
    }
});

btnCloseReport.addEventListener('click', () => {
    reportModal.style.display = 'none';
});

btnDownloadPdf.addEventListener('click', () => {
    const element = document.getElementById('report-document');
    element.classList.add('pdf-mode');

    const opt = {
        margin:       0,
        filename:     'Vayana_Voice_Session_Report.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };

    html2pdf().set(opt).from(element).save().then(() => {
        element.classList.remove('pdf-mode');
    });
});

