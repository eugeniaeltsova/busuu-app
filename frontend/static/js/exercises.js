// exercises.js — all exercise page logic
// `email` is injected inline from Jinja2 in exercises.html

var selectedType = 'short_story';
var currentExerciseId = null;
var currentQuestions = [];

// Translation state
var transSentences = [];
var transIndex = 0;
var transAnswers = [];
var transAnswerKey = {};
var transChecked = false;

// Gap-fill state
var gapAnswerKey = [];
var gapSlotCount = 0;
var draggedChipId = null;
var draggedFromSlot = null;

// ── General ───────────────────────────────────────────────────────────────────

function selectType(type, btn) {
  selectedType = type;
  document.querySelectorAll('.type-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
}

async function generateExercise() {
  var btn = document.getElementById('gen-btn');
  btn.disabled = true;
  btn.textContent = 'Generating...';
  showStatus('gen-status', 'Generating your exercise... this may take a few seconds.', 'info');

  document.getElementById('exercise-area').classList.remove('visible');
  document.getElementById('short-story-area').style.display = 'none';
  document.getElementById('translation-area').style.display = 'none';
  document.getElementById('gap-fill-area').style.display = 'none';
  document.getElementById('story-feedback-area').classList.remove('visible');
  document.getElementById('story-feedback-area').innerHTML = '';
  document.getElementById('translation-box').classList.remove('visible');
  document.getElementById('trans-summary').classList.remove('visible');
  document.getElementById('trans-per-feedback').className = 'trans-per-feedback';
  document.getElementById('trans-per-feedback').innerHTML = '';
  document.getElementById('gap-feedback-area').classList.remove('visible');
  document.getElementById('gap-feedback-area').innerHTML = '';
  var gapBtn = document.getElementById('gap-submit-btn');
  gapBtn.disabled = false;
  gapBtn.textContent = 'Check answers';

  try {
    var res = await fetch('/api/exercise/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email, exercise_type: selectedType }),
    });
    var data = await res.json();
    if (!res.ok) { showStatus('gen-status', 'Error: ' + data.detail, 'error'); return; }
    currentExerciseId = data.id;
    document.getElementById('gen-status').style.display = 'none';
    renderExercise(data);
    refreshHistory();
  } catch (err) {
    showStatus('gen-status', 'Network error — is the server running?', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate';
  }
}

async function refreshHistory() {
  try {
    var res = await fetch('/api/exercises/' + email);
    var exercises = await res.json();
    var card = document.getElementById('history-card');
    if (!card) return;

    var html = '<h2>Recent exercises</h2>';
    if (exercises.length === 0) {
      html += '<p style="color:#888780;font-size:.875rem;">No exercises yet.</p>';
    } else {
      exercises.forEach(function(ex) {
        var date = new Date(ex.created_at).toLocaleString([], {
          year: 'numeric', month: 'short', day: 'numeric',
          hour: '2-digit', minute: '2-digit'
        });
        var pill = '<span class="pill ' + ex.exercise_type + '">' + ex.exercise_type.replace('_', ' ') + '</span>';
        var completed = ex.completed ? ' · completed' : '';
        var difficulty = ex.difficulty ? ' · ' + ex.difficulty : '';
        var preview = ex.content ? ex.content.substring(0, 120) + '...' : '';
        var feedback = ex.feedback
          ? '<details style="margin-top:.5rem;"><summary style="font-size:.8rem;color:#534ab7;cursor:pointer;">Show feedback</summary><div style="margin-top:.5rem;font-size:.85rem;white-space:pre-wrap;color:#3a3a38;">' + ex.feedback + '</div></details>'
          : '';
        html += '<div class="history-item' + (ex.completed ? ' completed' : '') + '">' +
          '<div class="history-meta">' + pill + difficulty + ' · ' + date + completed + '</div>' +
          '<div class="history-preview">' + preview + '</div>' +
          feedback + '</div>';
      });
    }
    card.innerHTML = html;
  } catch (err) {
    console.error('refreshHistory failed:', err);
  }
}

function renderExercise(data) {
  var sd = data.structured_data;
  document.getElementById('difficulty-badge').textContent = data.difficulty || '';
  document.getElementById('exercise-area').classList.add('visible');
  if (data.exercise_type === 'short_story') {
    renderShortStory(sd);
  } else if (data.exercise_type === 'translation') {
    renderTranslation(sd, data.answer_key);
  } else if (data.exercise_type === 'gap_fill') {
    renderGapFill(sd, data.answer_key);
  }
}

// ── Short story ───────────────────────────────────────────────────────────────

function renderShortStory(sd) {
  document.getElementById('short-story-area').style.display = 'block';
  document.getElementById('translation-box').classList.remove('visible');
  document.getElementById('btn-reveal').textContent = 'Show translation';
  document.getElementById('story-title').textContent = sd.title || '';
  document.getElementById('story-text').textContent  = sd.story || '';
  document.getElementById('translation-box').textContent = sd.story_translation || '';
  currentQuestions = sd.questions || [];
  var list = document.getElementById('questions-list');
  list.innerHTML = '';
  currentQuestions.forEach(function(q, i) {
    var div = document.createElement('div');
    div.className = 'question-item';
    div.innerHTML =
      '<div class="question-text"><span class="question-num">Q' + (i+1) + '.</span>' + q.question + '</div>' +
      '<textarea id="answer-' + i + '" placeholder="Type your answer..." rows="2"></textarea>' +
      '<div class="voice-stub"><span>mic</span> Voice answer (coming soon)</div>';
    list.appendChild(div);
  });
}

function toggleTranslation(event) {
  var box = document.getElementById('translation-box');
  var btn = document.getElementById('btn-reveal');
  if (box.classList.contains('visible')) {
    box.classList.remove('visible');
    btn.textContent = 'Show translation';
  } else {
    box.classList.add('visible');
    btn.textContent = 'Hide translation';
  }
}

async function submitStoryAnswers() {
  var answers = currentQuestions.map(function(q, i) {
    return { question: q.question, answer: document.getElementById('answer-' + i).value.trim() };
  });
  var unanswered = answers.filter(function(a) { return !a.answer; }).length;
  if (unanswered > 0) { alert('Please answer all questions.'); return; }
  var btn = document.getElementById('story-submit-btn');
  btn.disabled = true;
  btn.textContent = 'Getting feedback...';
  try {
    var res = await fetch('/api/exercise/' + currentExerciseId + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_answer: JSON.stringify(answers) }),
    });
    var data = await res.json();
    if (!res.ok) { alert('Error: ' + data.detail); return; }
    var area = document.getElementById('story-feedback-area');
    area.innerHTML = '<div style="white-space:pre-wrap;font-size:.9rem;line-height:1.7;background:#f9f8f5;border-radius:8px;padding:1.25rem;">' + data.feedback + '</div>';
    area.classList.add('visible');
    area.scrollIntoView({ behavior: 'smooth', block: 'start' });
    refreshHistory();
  } catch (err) { alert('Network error.'); }
  finally { btn.disabled = false; btn.textContent = 'Submit answers'; }
}

// ── Translation ───────────────────────────────────────────────────────────────

function renderTranslation(sd, answerKeyJson) {
  transSentences = sd.sentences || [];
  transAnswers   = new Array(transSentences.length).fill('');
  transIndex     = 0;
  transChecked   = false;
  transAnswerKey = JSON.parse(answerKeyJson);
  document.getElementById('trans-total').textContent = transSentences.length;
  document.getElementById('translation-area').style.display = 'block';
  var dots = document.getElementById('trans-dots');
  dots.innerHTML = '';
  transSentences.forEach(function(_, i) {
    var dot = document.createElement('div');
    dot.className = 'trans-dot' + (i === 0 ? ' current' : '');
    dot.id = 'dot-' + i;
    dots.appendChild(dot);
  });
  showTransSentence(0);
}

function showTransSentence(index) {
  transChecked = false;
  document.getElementById('trans-current').textContent = index + 1;
  document.getElementById('trans-source').textContent  = transSentences[index].source;
  document.getElementById('trans-input').value = transAnswers[index] || '';
  document.getElementById('trans-input').disabled = false;
  document.getElementById('trans-input').focus();
  document.getElementById('trans-per-feedback').className = 'trans-per-feedback';
  document.getElementById('trans-per-feedback').innerHTML = '';
  document.getElementById('trans-next-btn').textContent = 'Check';
  transSentences.forEach(function(_, i) {
    var dot = document.getElementById('dot-' + i);
    dot.className = 'trans-dot' + (i === index ? ' current' : (transAnswers[i] ? ' done' : ''));
  });
}

async function transNext() {
  var input = document.getElementById('trans-input');
  var btn   = document.getElementById('trans-next-btn');
  if (!transChecked) {
    var answer = input.value.trim();
    if (!answer) { alert('Please type your translation first.'); return; }
    transAnswers[transIndex] = answer;
    input.disabled = true;
    var key = transAnswerKey[String(transSentences[transIndex].id)];
    var correct = key ? key.target : '';
    var notes   = key ? key.notes  : '';
    var fb = document.getElementById('trans-per-feedback');
    fb.innerHTML = '<strong>Correct answer:</strong> ' + correct +
      (notes ? '<div class="trans-correct-answer">Note: ' + notes + '</div>' : '');
    fb.className = 'trans-per-feedback correct';
    document.getElementById('dot-' + transIndex).className = 'trans-dot done';
    btn.textContent = transIndex < transSentences.length - 1 ? 'Next sentence' : 'Get overall feedback';
    transChecked = true;
  } else {
    if (transIndex < transSentences.length - 1) {
      transIndex++;
      showTransSentence(transIndex);
    } else {
      await submitTranslationFeedback();
    }
  }
}

async function submitTranslationFeedback() {
  var btn = document.getElementById('trans-next-btn');
  btn.disabled = true;
  btn.textContent = 'Getting feedback...';
  var payload = transSentences.map(function(s, i) {
    return { id: s.id, source: s.source, answer: transAnswers[i] };
  });
  try {
    var res = await fetch('/api/exercise/' + currentExerciseId + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_answer: JSON.stringify(payload) }),
    });
    var data = await res.json();
    if (!res.ok) { alert('Error: ' + data.detail); return; }
    document.getElementById('trans-overall-feedback').textContent = data.feedback || '';
    document.getElementById('trans-summary').classList.add('visible');
    document.getElementById('trans-summary').scrollIntoView({ behavior: 'smooth', block: 'start' });
    refreshHistory();
  } catch (err) { alert('Network error.'); }
  finally { btn.disabled = false; btn.textContent = 'Done'; }
}

// ── Gap-fill ──────────────────────────────────────────────────────────────────

function renderGapFill(sd, answerKeyJson) {
  var key = JSON.parse(answerKeyJson);
  gapAnswerKey = key.answers || [];
  gapSlotCount = gapAnswerKey.length;
  document.getElementById('gap-instructions').textContent = sd.instructions || '';
  document.getElementById('gap-fill-area').style.display = 'block';
  var bank = document.getElementById('word-bank');
  bank.innerHTML = '';
  (sd.word_bank || []).forEach(function(word, i) {
    var chip = document.createElement('div');
    chip.className = 'word-chip';
    chip.id = 'chip-' + i;
    chip.textContent = word;
    chip.draggable = true;
    chip.addEventListener('dragstart', function(e) { chipDragStart(e, i); });
    chip.addEventListener('dragend',   function(e) { chipDragEnd(e); });
    bank.appendChild(chip);
  });
  var rawText = sd.text_with_gaps || '';
  var parts = rawText.split('[___]');
  var container = document.getElementById('gap-text');
  container.innerHTML = '';
  var slotIndex = 0;
  parts.forEach(function(part, i) {
    if (part) container.appendChild(document.createTextNode(part));
    if (i < parts.length - 1) {
      var slot = document.createElement('span');
      slot.className = 'gap-slot';
      slot.id = 'slot-' + slotIndex;
      slot.dataset.index = slotIndex;
      slot.dataset.chipId = '';
      slot.textContent = '';
      slot.addEventListener('dragover',  function(e) { slotDragOver(e, parseInt(e.currentTarget.dataset.index)); });
      slot.addEventListener('dragleave', function(e) { slotDragLeave(e, parseInt(e.currentTarget.dataset.index)); });
      slot.addEventListener('drop',      function(e) { slotDrop(e, parseInt(e.currentTarget.dataset.index)); });
      slot.addEventListener('dragstart', function(e) { slotDragStart(e, parseInt(e.currentTarget.dataset.index)); });
      container.appendChild(slot);
      slotIndex++;
    }
  });
}

function chipDragStart(e, chipId) {
  draggedChipId = chipId;
  draggedFromSlot = null;
  e.dataTransfer.effectAllowed = 'move';
  setTimeout(function() { document.getElementById('chip-' + chipId).classList.add('dragging'); }, 0);
}

function chipDragEnd(e) {
  if (draggedChipId !== null) {
    var chip = document.getElementById('chip-' + draggedChipId);
    if (chip) chip.classList.remove('dragging');
  }
}

function slotDragStart(e, slotIndex) {
  var slot = document.getElementById('slot-' + slotIndex);
  if (!slot.dataset.chipId) { e.preventDefault(); return; }
  draggedFromSlot = slotIndex;
  draggedChipId   = parseInt(slot.dataset.chipId);
  e.dataTransfer.effectAllowed = 'move';
  slot.classList.add('dragging');
}

function slotDragOver(e, slotIndex) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  document.getElementById('slot-' + slotIndex).classList.add('drag-over');
}

function slotDragLeave(e, slotIndex) {
  document.getElementById('slot-' + slotIndex).classList.remove('drag-over');
}

function slotDrop(e, slotIndex) {
  e.preventDefault();
  var slot = document.getElementById('slot-' + slotIndex);
  slot.classList.remove('drag-over');
  if (draggedChipId === null) return;
  var chip = document.getElementById('chip-' + draggedChipId);
  if (slot.dataset.chipId !== '') {
    var evictedChipId = parseInt(slot.dataset.chipId);
    if (draggedFromSlot !== null) {
      var sourceSlot = document.getElementById('slot-' + draggedFromSlot);
      sourceSlot.textContent    = document.getElementById('chip-' + evictedChipId).textContent;
      sourceSlot.dataset.chipId = String(evictedChipId);
      sourceSlot.classList.add('filled');
      sourceSlot.draggable = true;
    } else {
      document.getElementById('chip-' + evictedChipId).style.display = 'inline-flex';
    }
  } else if (draggedFromSlot !== null) {
    var sourceSlot = document.getElementById('slot-' + draggedFromSlot);
    sourceSlot.textContent    = '';
    sourceSlot.dataset.chipId = '';
    sourceSlot.classList.remove('filled');
    sourceSlot.draggable = false;
  }
  slot.textContent    = chip.textContent;
  slot.dataset.chipId = String(draggedChipId);
  slot.classList.add('filled');
  slot.draggable = true;
  if (draggedFromSlot === null) chip.style.display = 'none';
  draggedChipId   = null;
  draggedFromSlot = null;
}

function bankDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  document.getElementById('word-bank').classList.add('drag-over');
}

function bankDrop(e) {
  e.preventDefault();
  document.getElementById('word-bank').classList.remove('drag-over');
  if (draggedFromSlot !== null && draggedChipId !== null) {
    var sourceSlot = document.getElementById('slot-' + draggedFromSlot);
    sourceSlot.textContent    = '';
    sourceSlot.dataset.chipId = '';
    sourceSlot.classList.remove('filled');
    sourceSlot.draggable = false;
    document.getElementById('chip-' + draggedChipId).style.display = 'inline-flex';
    draggedChipId   = null;
    draggedFromSlot = null;
  }
}

async function submitGapFill() {
  var userAnswers = [];
  var allFilled = true;
  for (var i = 0; i < gapSlotCount; i++) {
    var slot = document.getElementById('slot-' + i);
    var answer = slot.dataset.chipId !== '' ? slot.textContent.trim() : '';
    userAnswers.push(answer);
    if (!answer) allFilled = false;
  }
  if (!allFilled) { alert('Please fill in all gaps before checking.'); return; }
  var score = 0;
  for (var i = 0; i < gapSlotCount; i++) {
    var slot = document.getElementById('slot-' + i);
    var correct = gapAnswerKey[i] || '';
    if (userAnswers[i].toLowerCase() === correct.toLowerCase()) {
      slot.classList.add('correct');
      score++;
    } else {
      slot.classList.remove('filled');
      slot.classList.add('incorrect');
      var hint = document.createElement('span');
      hint.className = 'gap-correct-word';
      hint.textContent = correct;
      slot.appendChild(hint);
    }
    slot.draggable = false;
  }
  var btn = document.getElementById('gap-submit-btn');
  btn.disabled = true;
  btn.textContent = 'Getting feedback...';
  try {
    var payload = { answers: userAnswers, score: score + '/' + gapSlotCount };
    var res = await fetch('/api/exercise/' + currentExerciseId + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_answer: JSON.stringify(payload) }),
    });
    var data = await res.json();
    if (!res.ok) { alert('Error: ' + data.detail); return; }
    var fbArea = document.getElementById('gap-feedback-area');
    fbArea.textContent = data.feedback || '';
    fbArea.classList.add('visible');
    fbArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    refreshHistory();
  } catch (err) { alert('Network error.'); }
  finally { btn.textContent = score + '/' + gapSlotCount + ' correct'; }
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function showStatus(id, msg, type) {
  var el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'status ' + type;
}

// Convert UTC timestamps to local time on page load
document.querySelectorAll('.ex-time').forEach(function(el) {
  el.textContent = new Date(el.dataset.utc).toLocaleString([], {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
});
