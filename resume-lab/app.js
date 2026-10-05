'use strict';
const $ = id => document.getElementById(id);
let current = null, busy = false, view = 'source', token = '', uploaded = null;
const history = [];
function profileText(profile) {
  const lines = [profile.full_name || 'Name not extracted'];
  if (profile.contact_email) lines.push(`Email: ${profile.contact_email}`);
  if (profile.contact_phone) lines.push(`Phone: ${profile.contact_phone}`);
  lines.push('', 'Skills', profile.skills.length ? profile.skills.join(', ') : 'Not extracted');
  lines.push('', 'Experience');
  if (!profile.experience.length) lines.push('Not extracted');
  for (const job of profile.experience) {
    lines.push([job.role, job.company].filter(Boolean).join(', '));
    const dates = [job.start_date, job.end_date].filter(Boolean).join(' – ');
    if (dates) lines.push(dates);
    for (const achievement of job.achievements) lines.push(`• ${achievement.replace(/^\s*[-*•]\s*/, '')}`);
    lines.push('');
  }
  lines.push('', 'Education');
  if (!profile.education.length) lines.push('Not extracted');
  for (const education of profile.education) {
    lines.push([education.institution, education.degree, education.field_of_study, education.graduation_year].filter(Boolean).join(', '));
  }
  if (profile.languages.length) lines.push('', `Languages: ${profile.languages.join(', ')}`);
  return lines.join('\n');
}
function render() {
  if (view === 'history') $('result').textContent = JSON.stringify(history, null, 2);
  else if (current) $('result').textContent = view === 'source' ? current.source_text :
    current.profile ? (view === 'json' ? JSON.stringify(current.profile, null, 2) : profileText(current.profile)) : 'Text preview only. Uncheck text preview and scan to extract a profile automatically.';
  for (const tab of ['source', 'profile', 'json', 'history']) $(tab + '-tab').setAttribute('aria-pressed', String(tab === view));
}
async function refresh() {
  try {
    const session = await fetch('/api/session'); token = (await session.json()).token;
    const response = await fetch('/api/policy'); const data = await response.json();
    $('connection').textContent = response.ok ? (data.ocr.length ? 'Automatic scanning is ready. All processing stays local.' : 'Text extraction is ready. OCR models are unavailable.') : `${data.error || 'Automatic scanning unavailable.'} Text preview is available for readable files.`;
  } catch { $('connection').textContent = 'Cannot connect to the local server. Reload after starting it.'; }
}
function encode(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('Unable to read this file.'));
    reader.readAsDataURL(file);
  });
}
async function run() {
  if (busy) return;
  $('error').hidden = true;
  if (!uploaded) { $('error').textContent = 'Choose a resume first.'; $('error').hidden = false; return; }
  busy = true; current = null; $('download').disabled = true;
  for (const id of ['run','file','sample','parse','refresh']) $(id).disabled = true;
  $('status').textContent = 'Processing locally… OCR and extraction may take several minutes.';
  $('result').textContent = 'Scanning…'; $('metrics').replaceChildren();
  $('diagnostics').textContent = 'Waiting for model choices and results…';
  try {
    if (uploaded.size > 8 * 1024 * 1024) throw new Error('Upload a file no larger than 8 MB.');
    const response = await fetch('/api/scan', {method:'POST', headers:{'Content-Type':'application/json','X-Lab-Token':token},
      body:JSON.stringify({filename:uploaded.name, data:await encode(uploaded), parse_only:$('parse').checked})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Scan failed.');
    current = data;
    $('diagnostics').textContent = JSON.stringify({policy:data.policy_id, extraction_model:data.model, ocr_models:data.ocr_models, extraction_attempts:data.extraction_attempts, ocr_pages:data.ocr_pages, source_repairs:data.source_repairs || []}, null, 2);
    view = data.profile ? 'profile' : 'source';
    history.unshift({file:data.filename, model:data.model, ocr_model:data.ocr_model, mode:data.mode, seconds:data.elapsed_seconds, schema_valid:data.schema_valid});
    if (history.length > 30) history.pop();
    for (const text of [data.route, `${data.elapsed_seconds}s`, data.mode === 'live' ? 'Live extraction · schema valid' : data.ocr_used ? 'Live OCR · extraction not run' : 'Text preview · AI not tested']) {
      const badge = document.createElement('span'); badge.className = 'metric'; badge.textContent = text; $('metrics').append(badge);
    }
    $('status').textContent = `Finished: ${data.filename}`;
    $('warning').textContent = data.warnings.join(' ') || (data.ocr_used ? `Source transcribed by ${data.ocr_model}. Review OCR accuracy against the original document. Extraction was not run.` : 'Text preview only. No AI accuracy score or model recommendation was generated.');
    $('download').disabled = false; render();
  } catch (error) {
    $('error').textContent = error.message; $('error').hidden = false;
    $('status').textContent = 'Scan failed. No candidate profile was created.';
    $('result').textContent = 'Resolve the error above and retry.';
  } finally {
    busy = false; for (const id of ['run','file','sample','parse','refresh']) $(id).disabled = false;
  }
}
$('file').addEventListener('change', () => { uploaded = $('file').files[0]; if(uploaded) run(); });
$('run').addEventListener('click', run); $('refresh').addEventListener('click', refresh);
$('sample').addEventListener('click', () => {
  uploaded = new File(['# Mira Example\nEmail: mira@example.com\n\nSkills: Python, SQL, Docker\n\nExperience\nSoftware Engineer, Example Studio\n2022 - 2025\nBuilt internal reporting tools using Python and SQL.\n\nEducation\nExample University, BSc Computer Science, 2022\n\nLanguages: Thai, English'], 'synthetic-resume.txt', {type:'text/plain'});
  $('file').value = ''; $('parse').checked = false; run();
});
for (const tab of ['source','profile','json','history']) $(tab+'-tab').addEventListener('click', () => {view=tab;render();});
$('download').addEventListener('click', () => {
  if(!current) return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));
  const anchor=document.createElement('a');anchor.href=url;anchor.download='resume-scan.json';anchor.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
refresh();
