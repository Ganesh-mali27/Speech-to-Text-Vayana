const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const selectedFileDiv = document.getElementById('selected-file');
const fileNameSpan = document.getElementById('file-name');
const uploadBtn = document.getElementById('upload-btn');
const uploadSection = document.getElementById('upload-section');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const statusText = document.getElementById('status-text');
const statusMessage = document.getElementById('status-message');
const audioPlayer = document.getElementById('audio-player');
const intentTableBody = document.querySelector('#intent-table tbody');
const transcriptContent = document.getElementById('transcript-content');

let currentFile = null;

// Drag and drop handlers
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
    }
});

function pollStatus(taskId) {
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
    resultsSection.style.display = 'flex';

    // Set audio source
    audioPlayer.src = `/api/audio/${data.audio_filename}`;

    // Clear previous data
    intentTableBody.innerHTML = '';
    transcriptContent.innerHTML = '';

    // We use intent_data as it contains both transliterated_text and intent analysis per segment
    data.intent_data.forEach(segment => {
        // 1. Populate Transcript
        const transcriptDiv = document.createElement('div');
        transcriptDiv.className = 'transcript-segment';
        transcriptDiv.innerHTML = `
            <div class="speaker">${segment.speaker}</div>
            <div class="text">${segment.transliterated_text}</div>
        `;
        transcriptContent.appendChild(transcriptDiv);

        // 2. Populate Intent Table
        const tr = document.createElement('tr');
        
        const keywordsHTML = segment.flagged_keywords.length > 0 
            ? segment.flagged_keywords.map(k => `<span class="keyword-tag">${k}</span>`).join('') 
            : '-';
            
        const intentsHTML = segment.intent_detected.length > 0
            ? segment.intent_detected.map(i => `<span class="intent-tag">${i}</span>`).join('')
            : '-';

        const riskClass = segment.risk_confidence.level === 'high' ? 'risk-high' : 'risk-low';

        tr.innerHTML = `
            <td><span class="speaker-badge">${segment.speaker}</span></td>
            <td>${keywordsHTML}</td>
            <td>${intentsHTML}</td>
            <td class="${riskClass}">${segment.risk_confidence.percentage}</td>
        `;
        intentTableBody.appendChild(tr);
    });
}
