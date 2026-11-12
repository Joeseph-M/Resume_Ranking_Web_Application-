const form = document.getElementById('rank-form');
const folderInput = document.getElementById('resume-folder'); 
const folderTitle = document.getElementById('folder-title'); 
const folderSubtitle = document.getElementById('folder-count'); 
const fileCount = document.getElementById('file-count');
const statusBox = document.getElementById('status'); 
const rankButton = document.getElementById('rank-button'); 
const results = document.getElementById('results'); 
const resultsBody = document.getElementById('results-body'); 
const downloadLink = document.getElementById('download-link'); 
const exportLocation = document.getElementById('export-location'); 
const skippedNote = document.getElementById('skipped-note'); 

function showStatus (message, working = false) {
    statusBox.textContent = message; 
    statusBox.hidden = false;
    statusBox.classList.toggle('is-working', working); 
}

function addCell(row, content, className) {
    const cell = document.createElement('td');
    if (className) cell.className = className; 
    if (content instanceof Node) cell.appendChild(content); 
    else cell.textContent = content; 
    row.appendChild(cell); 
    return cell; 
}

folderInput.addEventListener('change', () => {
  const files = Array.from(folderInput.files || []);
  const supported = files.filter((file) => /\.(pdf|doc|docx|txt|rtf|odt|html?|md)$/i.test(file.name));
  const folderName = files[0]?.webkitRelativePath?.split('/')[0];
  folderTitle.textContent = folderName || (files.length ? 'Selected folder' : 'Choose a folder');
  folderSubtitle.textContent = supported.length
    ? `${supported.length} supported resume${supported.length === 1 ? '' : 's'} found`
    : 'PDF, DOC, DOCX, TXT, RTF, ODT and HTML';
  fileCount.textContent = files.length
    ? `${supported.length} supported file${supported.length === 1 ? '' : 's'} selected`
    : 'Your selected files stay on this computer.';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  results.hidden = true;
  resultsBody.replaceChildren();
  skippedNote.hidden = true;
  rankButton.disabled = true;
  rankButton.querySelector('span:first-child').textContent = 'Ranking…';
  showStatus('Reading resume text and comparing it with the job description…', true);

  try {
    const response = await fetch('/rank', { method: 'POST', body: new FormData(form) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'The resumes could not be ranked.');

    payload.items.forEach((item) => {
      const row = document.createElement('tr');
      addCell(row, String(item.rank).padStart(2, '0'), 'rank-number');
      addCell(row, item.filename, 'resume-name');
      const score = document.createElement('span');
      score.className = 'score';
      score.textContent = `${item.score.toFixed(1)}%`;
      addCell(row, score, 'score-cell');
      const matched = item.matched_terms.length ? item.matched_terms.join(' · ') : 'No shared key terms detected';
      addCell(row, matched, 'term-list');
      resultsBody.appendChild(row);
    });

    downloadLink.href = payload.download_url;
    exportLocation.textContent = `Saved folder: ${payload.output_folder}`;
    if (payload.skipped?.length) {
      const names = payload.skipped.map((item) => `${item.filename} — ${item.reason}`).join(' · ');
      skippedNote.textContent = `Skipped ${payload.skipped.length} unreadable or unsupported file${payload.skipped.length === 1 ? '' : 's'}: ${names}`;
      skippedNote.hidden = false;
    }
    results.hidden = false;
    statusBox.hidden = true;
    results.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) {
    showStatus(error.message || 'Something went wrong while ranking the resumes.');
  } finally {
    rankButton.disabled = false;
    rankButton.querySelector('span:first-child').textContent = 'Rank resumes';
  }
});