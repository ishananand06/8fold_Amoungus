// ===== Among Us LLM Replay Theater — App Logic =====

// --- Room Layout (Skeld-inspired spatial positioning) ---
// Room positions matched to map.png (836×470)
const ROOM_DEFS = {
  'Cafeteria':      { x: 350, y: 15,  w: 185, h: 175, shape: 'octagon' },
  'Weapons':        { x: 585, y: 65,  w: 90, h: 80,  shape: 'rect' },
  'O2':             { x: 530, y: 165, w: 80,  h: 65,  shape: 'rect' },
  'Navigation':     { x: 740, y: 170, w: 60,  h: 90,  shape: 'rect' },
  'Shields':        { x: 585, y: 315, w: 90,  h: 85,  shape: 'rect' },
  'Communications': { x: 490, y: 385, w: 90, h: 55,  shape: 'rect' },
  'Storage':        { x: 370, y: 295, w: 100, h: 150,  shape: 'rect' },
  'Admin':          { x: 490, y: 240, w: 90,  h: 75,  shape: 'rect' },
  'Electrical':     { x: 260, y: 275, w: 95,  h: 65,  shape: 'rect' },
  'Lower Engine':   { x: 110, y: 300, w: 80, h: 75,  shape: 'rect' },
  'Security':       { x: 195, y: 185, w: 50,  h: 75,  shape: 'rect' },
  'Reactor':        { x: 40,  y: 175, w: 70, h: 100,  shape: 'rect' },
  'Upper Engine':   { x: 100,  y: 65,  w: 105, h: 80,  shape: 'rect' },
  'MedBay':         { x: 255, y: 155, w: 80,  h: 75,  shape: 'rect' },
};

// Corridors as path segments between rooms
const ADJACENCY = {
  'Cafeteria':      ['Weapons', 'MedBay', 'Upper Engine', 'Admin', 'Storage'],
  'Weapons':        ['Cafeteria', 'O2', 'Navigation'],
  'O2':             ['Weapons', 'Navigation', 'Shields', 'Admin'],
  'Navigation':     ['Weapons', 'O2', 'Shields'],
  'Shields':        ['Navigation', 'O2', 'Communications', 'Storage'],
  'Communications': ['Shields', 'Storage'],
  'Storage':        ['Cafeteria', 'Admin', 'Communications', 'Shields', 'Electrical'],
  'Admin':          ['Cafeteria', 'Storage', 'O2'],
  'Electrical':     ['Storage', 'Lower Engine', 'Security'],
  'Lower Engine':   ['Electrical', 'Security', 'Reactor'],
  'Security':       ['Upper Engine', 'Lower Engine', 'Reactor', 'Electrical'],
  'Reactor':        ['Upper Engine', 'Lower Engine', 'Security'],
  'Upper Engine':   ['Cafeteria', 'MedBay', 'Security', 'Reactor'],
  'MedBay':         ['Upper Engine', 'Cafeteria'],
};

// --- State ---
let gameData = null;
let currentRoundIdx = 0;
let totalRounds = 0;
let isPlaying = false;
let playSpeed = 1.0;
let playTimer = null;

// --- DOM Refs ---
const fileInput       = document.getElementById('fileInput');
const fileName        = document.getElementById('fileName');
const mapSvg          = document.getElementById('mapSvg');
const corridorsG      = document.getElementById('corridors');
const roomsG          = document.getElementById('rooms');
const bodiesG         = document.getElementById('bodies');
const playersG        = document.getElementById('players');
const roundBadge      = document.getElementById('roundNumber');
const gameResultDiv   = document.getElementById('gameResult');
const resultText      = document.getElementById('resultText');
const noFileOverlay   = document.getElementById('noFileOverlay');
const roundInfoTab    = document.getElementById('roundInfo');
const chatLogTab      = document.getElementById('chatLog');
const prevBtn         = document.getElementById('prevBtn');
const nextBtn         = document.getElementById('nextBtn');
const playBtn         = document.getElementById('playBtn');
const playIcon        = document.getElementById('playIcon');
const pauseIcon       = document.getElementById('pauseIcon');
const roundSlider     = document.getElementById('roundSlider');
const roundLabel      = document.getElementById('roundLabel');
const speedDown       = document.getElementById('speedDown');
const speedUp         = document.getElementById('speedUp');
const speedLabel      = document.getElementById('speedLabel');
const meetingOverlay  = document.getElementById('meetingOverlay');
const meetingMeta     = document.getElementById('meetingMeta');
const meetingTranscript = document.getElementById('meetingTranscript');
const meetingResult   = document.getElementById('meetingResult');
const closeMeetingBtn = document.getElementById('closeMeeting');

// --- Init ---
function init() {
  drawMapStatic();
  bindEvents();
}

// ===== MAP DRAWING =====

function roomCenter(name) {
  const r = ROOM_DEFS[name];
  return { x: r.x + r.w / 2, y: r.y + r.h / 2 };
}

function drawMapStatic() {
  // Add map background image
  const existingBg = mapSvg.querySelector('.map-bg');
  if (!existingBg) {
    const bg = createSvgEl('image', {
      href: 'map.png',
      x: 0, y: 0,
      width: 836, height: 470,
      class: 'map-bg',
      preserveAspectRatio: 'xMidYMid meet',
    });
    // Insert as first child so it's behind everything
    mapSvg.insertBefore(bg, mapSvg.firstChild);
  }

  // Corridors hidden — the map image already shows connections
  corridorsG.innerHTML = '';

  // Draw rooms as invisible hit areas (map image is the visual)
  roomsG.innerHTML = '';
  for (const [name, def] of Object.entries(ROOM_DEFS)) {
    const g = createSvgEl('g', { 'data-room': name });

    // Invisible shape for interaction and state highlighting
    const shape = createSvgEl('rect', {
      x: def.x, y: def.y, width: def.w, height: def.h,
      rx: 4, ry: 4,
      class: 'room-shape',
      id: `room-${name}`,
    });
    g.appendChild(shape);

    roomsG.appendChild(g);
  }
}

function createSvgEl(tag, attrs = {}) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

// ===== GAME DATA =====

function loadGame(data) {
  gameData = data;
  totalRounds = data.game_log.length;
  currentRoundIdx = 0;

  roundSlider.max = totalRounds - 1;
  roundSlider.value = 0;

  noFileOverlay.classList.add('hidden');

  // Show game result on the badge if present
  if (data.winner) {
    gameResultDiv.classList.remove('hidden', 'crewmates-win', 'impostors-win');
    const isCrewWin = data.winner === 'crewmates';
    gameResultDiv.classList.add(isCrewWin ? 'crewmates-win' : 'impostors-win');
    const causeLabel = (data.cause || '').replace(/_/g, ' ');
    resultText.textContent = `${data.winner.toUpperCase()} WIN — ${causeLabel.toUpperCase()}`;
  } else {
    gameResultDiv.classList.add('hidden');
  }

  updateDisplay();
}

// ===== DISPLAY UPDATE =====

function updateDisplay() {
  if (!gameData) return;
  const log = gameData.game_log[currentRoundIdx];
  const state = log.state || {};
  const rNum = log.round || currentRoundIdx + 1;
  const lastRound = gameData.game_log[totalRounds - 1].round || totalRounds;

  // Round badge
  roundBadge.textContent = String(rNum).padStart(2, '0');
  roundLabel.textContent = `${rNum} / ${lastRound}`;
  roundSlider.value = currentRoundIdx;

  // Show/hide game result only on last round
  if (gameData.winner) {
    gameResultDiv.classList.toggle('hidden', currentRoundIdx !== totalRounds - 1);
  }

  updateRoomStates(state);
  updateBodies(state);
  updatePlayers(state);
  updateRoundInfo(log);
  updateChatTranscript(rNum);
}

function updateRoomStates(state) {
  const sab = state.sabotage;
  const sabRooms = sab ? Object.keys(sab.fix_progress || {}) : [];
  const bodyRooms = (state.bodies || []).map(b => b.location);

  for (const name of Object.keys(ROOM_DEFS)) {
    const shape = document.getElementById(`room-${name}`);
    if (!shape) continue;
    shape.classList.toggle('sabotaged', sabRooms.includes(name));
    shape.classList.toggle('has-body', bodyRooms.includes(name));
  }
}

function updateBodies(state) {
  bodiesG.innerHTML = '';
  const bodies = state.bodies || [];
  // Group by location
  const byRoom = {};
  for (const b of bodies) {
    if (!byRoom[b.location]) byRoom[b.location] = [];
    byRoom[b.location].push(b);
  }

  for (const [room, bs] of Object.entries(byRoom)) {
    if (!ROOM_DEFS[room]) continue;
    const center = roomCenter(room);
    const g = createSvgEl('g', { class: 'body-marker' });

    // Red circle indicator
    const circle = createSvgEl('circle', {
      cx: center.x, cy: center.y + 18,
      r: 10,
      fill: 'rgba(255,0,64,0.25)',
      stroke: '#ff0040',
      'stroke-width': 1.5,
    });
    g.appendChild(circle);

    // Skull emoji text
    const skull = createSvgEl('text', {
      x: center.x, y: center.y + 19,
      class: 'body-skull',
    });
    skull.textContent = '☠';
    g.appendChild(skull);

    // Count label
    if (bs.length > 1) {
      const countLabel = createSvgEl('text', {
        x: center.x + 12, y: center.y + 14,
        fill: '#ff0040',
        'font-size': '10',
        'font-weight': '700',
        'font-family': 'var(--font-mono)',
      });
      countLabel.textContent = `×${bs.length}`;
      g.appendChild(countLabel);
    }

    bodiesG.appendChild(g);
  }
}

function updatePlayers(state) {
  const playerLocs = state.player_locations || {};
  const alivePlayers = state.alive_players || [];
  const allRoles = gameData.all_roles || {};

  // Group players by room
  const roomStacks = {};
  for (const [pid, loc] of Object.entries(playerLocs)) {
    if (!roomStacks[loc]) roomStacks[loc] = [];
    roomStacks[loc].push(pid);
  }

  // Remove old players that no longer exist
  const existingGroups = playersG.querySelectorAll('.player-group');
  const currentPids = new Set(Object.keys(playerLocs));
  existingGroups.forEach(g => {
    if (!currentPids.has(g.dataset.pid)) g.remove();
  });

  // Create or update each player
  for (const [loc, pids] of Object.entries(roomStacks)) {
    if (!ROOM_DEFS[loc]) continue;
    const center = roomCenter(loc);

    pids.sort();
    const cols = Math.min(pids.length, 4);

    for (let i = 0; i < pids.length; i++) {
      const pid = pids[i];
      const col = i % cols;
      const row = Math.floor(i / cols);
      const offsetX = (col - (cols - 1) / 2) * 28;
      const offsetY = row * 28 + 16;

      const tx = center.x + offsetX;
      const ty = center.y + offsetY;

      const isAlive = alivePlayers.includes(pid);
      const role = allRoles[pid] || 'crewmate';
      const color = role === 'crewmate' ? '#f5c842' : '#ff3e3e';

      let group = playersG.querySelector(`[data-pid="${pid}"]`);
      if (!group) {
        group = createPlayerToken(pid, color);
        playersG.appendChild(group);
      }

      // Update position
      group.setAttribute('transform', `translate(${tx}, ${ty})`);

      // Update alive/dead state
      group.classList.toggle('dead', !isAlive);

      // Update color (in case of re-render)
      const body = group.querySelector('.player-body');
      if (body && isAlive) body.setAttribute('fill', color);
    }
  }
}

function createPlayerToken(pid, color) {
  const g = createSvgEl('g', {
    class: 'player-group',
    'data-pid': pid,
  });

  // Body (rounded rect like among us character silhouette)
  const body = createSvgEl('rect', {
    x: -9, y: -11, width: 18, height: 20, rx: 7, ry: 7,
    class: 'player-body',
    fill: color,
  });
  g.appendChild(body);

  // Visor
  const visor = createSvgEl('ellipse', {
    cx: 4, cy: -4, rx: 5, ry: 3.5,
    class: 'player-visor',
  });
  g.appendChild(visor);

  // Backpack bump
  const backpack = createSvgEl('rect', {
    x: -13, y: -4, width: 5, height: 10, rx: 2.5, ry: 2.5,
    fill: color, opacity: 0.7,
    class: 'player-body',
  });
  g.appendChild(backpack);

  // Label
  const label = createSvgEl('text', {
    x: 0, y: 20,
    class: 'player-label',
  });
  label.textContent = pid.replace('player_', 'P');
  g.appendChild(label);

  return g;
}

// ===== ROUND INFO =====

function updateRoundInfo(log) {
  const actions = log.actions || {};
  const results = log.results || {};
  const allRoles = gameData.all_roles || {};

  let html = '';
  for (const pid of Object.keys(actions).sort()) {
    const act = actions[pid];
    const res = results[pid] || {};
    const role = allRoles[pid] || 'crewmate';
    const roleClass = role === 'crewmate' ? 'crewmate' : 'impostor';
    const isSuccess = res.success;
    const statusClass = isSuccess ? 'success' : 'fail';
    const statusText = isSuccess ? 'SUCCESS' : `FAILED — ${res.reason || 'unknown'}`;

    html += `
      <div class="action-entry ${statusClass}">
        <div class="action-player ${roleClass}">${pid}</div>
        <div class="action-detail">${act.action}${act.target ? ' → ' + act.target : ''}</div>
        <div class="action-result ${statusClass}">${statusText}</div>
      </div>
    `;
  }

  roundInfoTab.innerHTML = html || '<div class="tab-placeholder">No actions this round</div>';
}

// ===== CHAT TRANSCRIPT =====

function updateChatTranscript(roundNum) {
  const meetings = gameData.meeting_history || [];
  const currentMeetings = meetings.filter(m => m.round_called === roundNum);

  if (currentMeetings.length === 0) {
    chatLogTab.innerHTML = '<div class="no-meeting">No meeting this round.</div>';
    return;
  }

  let html = '';
  for (const m of currentMeetings) {
    html += `<div class="chat-header">EMERGENCY MEETING — ROUND ${roundNum}</div>`;
    html += `<div class="chat-meta">
      Trigger: <strong>${m.trigger}</strong> &nbsp;|&nbsp; Called by: <strong>${m.called_by}</strong>
      ${m.body_found ? `<br>Body found: <strong>${m.body_found}</strong> in <strong>${m.body_location}</strong>` : ''}
    </div>`;

    // Transcript messages
    const transcript = m.transcript || [];
    for (const msg of transcript) {
      const role = gameData.all_roles[msg.speaker] || 'crewmate';
      const roleClass = role === 'crewmate' ? 'crewmate' : 'impostor';
      html += `
        <div class="chat-msg ${roleClass}-msg">
          <div class="chat-speaker ${roleClass}">
            ${msg.speaker}
            <span class="chat-rotation">R${msg.rotation}</span>
          </div>
          <div class="chat-text">${escapeHtml(msg.message)}</div>
        </div>
      `;
    }

    // Vote result
    let resultLabel = 'NO EJECTION — SKIPPED';
    if (m.voted_out) {
      resultLabel = `${m.voted_out} EJECTED (${m.role_revealed})`;
    }
    html += `<div class="chat-vote-result">${resultLabel}</div>`;

    // Vote tally
    if (m.vote_tally) {
      html += '<div class="vote-tally">';
      for (const [target, count] of Object.entries(m.vote_tally)) {
        html += `<span class="vote-tally-item">${target}: <span class="vote-count">${count}</span></span>`;
      }
      html += '</div>';
    }
  }

  chatLogTab.innerHTML = html;
}

// ===== MEETING OVERLAY =====

function showMeeting(meeting) {
  meetingOverlay.classList.remove('hidden');

  meetingMeta.innerHTML = `
    Round <strong>${meeting.round_called}</strong> &nbsp;|&nbsp;
    Trigger: <strong>${meeting.trigger}</strong> &nbsp;|&nbsp;
    Called by: <strong>${meeting.called_by}</strong>
    ${meeting.body_found ? `<br>Body: <strong>${meeting.body_found}</strong> in <strong>${meeting.body_location}</strong>` : ''}
  `;

  let tHtml = '';
  for (const msg of (meeting.transcript || [])) {
    const role = gameData.all_roles[msg.speaker] || 'crewmate';
    const roleClass = role === 'crewmate' ? 'crewmate' : 'impostor';
    tHtml += `
      <div class="meeting-msg ${roleClass}-msg">
        <div class="msg-speaker ${roleClass}">
          ${msg.speaker}
          <span class="msg-rotation">R${msg.rotation}</span>
        </div>
        <div class="msg-text">${escapeHtml(msg.message)}</div>
      </div>
    `;
  }
  meetingTranscript.innerHTML = tHtml;

  let rText = 'NO EJECTION — SKIPPED';
  if (meeting.voted_out) {
    rText = `${meeting.voted_out.toUpperCase()} EJECTED (${(meeting.role_revealed || '').toUpperCase()})`;
  }
  meetingResult.textContent = rText;
}

function hideMeeting() {
  meetingOverlay.classList.add('hidden');
}

// ===== PLAYBACK =====

function play() {
  isPlaying = true;
  playBtn.classList.add('playing');
  playIcon.classList.add('hidden');
  pauseIcon.classList.remove('hidden');
  scheduleNext();
}

function pause() {
  isPlaying = false;
  playBtn.classList.remove('playing');
  playIcon.classList.remove('hidden');
  pauseIcon.classList.add('hidden');
  clearTimeout(playTimer);
}

function togglePlay() {
  if (isPlaying) pause();
  else play();
}

function scheduleNext() {
  clearTimeout(playTimer);
  if (!isPlaying) return;
  const delay = Math.max(200, playSpeed * 1000);
  playTimer = setTimeout(() => {
    if (currentRoundIdx < totalRounds - 1) {
      currentRoundIdx++;
      updateDisplay();

      // Check for meeting — auto-show
      const rNum = gameData.game_log[currentRoundIdx].round || currentRoundIdx + 1;
      const meeting = (gameData.meeting_history || []).find(m => m.round_called === rNum);
      if (meeting) {
        pause();
        showMeeting(meeting);
        return;
      }

      scheduleNext();
    } else {
      pause();
    }
  }, delay);
}

function goToRound(idx) {
  currentRoundIdx = Math.max(0, Math.min(totalRounds - 1, idx));
  updateDisplay();
}

function setSpeed(val) {
  playSpeed = Math.max(0.2, Math.min(3.0, val));
  speedLabel.textContent = `${playSpeed.toFixed(1)}×`;
}

// ===== EVENTS =====

function bindEvents() {
  // File load
  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    fileName.textContent = file.name;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const data = JSON.parse(ev.target.result);
        loadGame(data);
      } catch (err) {
        alert('Failed to parse JSON: ' + err.message);
      }
    };
    reader.readAsText(file);
  });

  // Controls
  prevBtn.addEventListener('click', () => { if (currentRoundIdx > 0) { currentRoundIdx--; updateDisplay(); } });
  nextBtn.addEventListener('click', () => { if (currentRoundIdx < totalRounds - 1) { currentRoundIdx++; updateDisplay(); } });
  playBtn.addEventListener('click', togglePlay);
  roundSlider.addEventListener('input', (e) => goToRound(parseInt(e.target.value)));
  speedDown.addEventListener('click', () => setSpeed(playSpeed + 0.2));
  speedUp.addEventListener('click', () => setSpeed(playSpeed - 0.2));
  closeMeetingBtn.addEventListener('click', hideMeeting);

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    // Don't trigger if overlay is open (except Escape)
    if (e.key === 'Escape') { hideMeeting(); return; }
    if (!meetingOverlay.classList.contains('hidden')) return;
    if (!gameData) return;

    switch (e.key) {
      case ' ':
        e.preventDefault();
        togglePlay();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        pause();
        if (currentRoundIdx > 0) { currentRoundIdx--; updateDisplay(); }
        break;
      case 'ArrowRight':
        e.preventDefault();
        pause();
        if (currentRoundIdx < totalRounds - 1) { currentRoundIdx++; updateDisplay(); }
        break;
      case '+':
      case '=':
        setSpeed(playSpeed - 0.2);
        break;
      case '-':
      case '_':
        setSpeed(playSpeed + 0.2);
        break;
      case 'm':
      case 'M': {
        // Toggle meeting overlay for current round
        const rNum = gameData.game_log[currentRoundIdx].round || currentRoundIdx + 1;
        const meeting = (gameData.meeting_history || []).find(m => m.round_called === rNum);
        if (meeting) showMeeting(meeting);
        break;
      }
    }
  });
}

// ===== UTILS =====

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ===== START =====
init();
