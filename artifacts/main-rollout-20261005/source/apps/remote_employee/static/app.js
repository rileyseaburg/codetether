import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Room, RoomEvent, Track } from 'livekit-client';

const basePath = window.location.pathname.startsWith('/remote-employee')
  ? '/remote-employee' : '';

const state = {
  employees: [],
  proposals: [],
  tasks: [],
  selectedId: null,
  room: null,
  roomKind: null,
  avatars: new Map(),
  speaking: new Set(),
  refreshing: false,
};

const $ = (selector) => document.querySelector(selector);
const el = {
  roster: $('#roster'),
  emptyRoster: $('#empty-roster'),
  proposals: $('#proposals'),
  proposalCount: $('#proposal-count'),
  placeholder: $('#employee-placeholder'),
  detail: $('#employee-detail'),
  toast: $('#toast'),
  livekitStatus: $('#livekit-status'),
  muxStatus: $('#mux-status'),
  officeButton: $('#office-button'),
  leaveButton: $('#leave-button'),
  micButton: $('#mic-button'),
  cameraButton: $('#camera-button'),
  meetingLabel: $('#meeting-label'),
  meetingRoom: $('#meeting-room'),
  videoStage: $('#video-stage'),
  audioStage: $('#audio-stage'),
};

let toastTimer;
function notify(message, error = false) {
  clearTimeout(toastTimer);
  el.toast.textContent = message;
  el.toast.className = `toast show${error ? ' error' : ''}`;
  toastTimer = setTimeout(() => { el.toast.className = 'toast'; }, 3200);
}

function ceoToken() {
  return sessionStorage.getItem('remoteEmployeeToken') || '';
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (ceoToken()) headers.set('Authorization', `Bearer ${ceoToken()}`);
  const response = await fetch(`${basePath}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch (_) { /* non-JSON */ }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function initials(name) {
  return name.split(/\s+/).slice(0, 2).map((word) => word[0]).join('').toUpperCase();
}

function shortPath(path) {
  if (path.length < 34) return path;
  return `…/${path.split('/').slice(-2).join('/')}`;
}

function selectedEmployee() {
  return state.employees.find((employee) => employee.id === state.selectedId);
}

async function refresh() {
  if (state.refreshing) return;
  state.refreshing = true;
  try {
    const company = await api('/api/company');
    state.employees = company.employees;
    state.tasks = company.tasks;
    state.proposals = company.proposals;
    el.muxStatus.classList.add('online');
    if (state.selectedId && !selectedEmployee()) state.selectedId = null;
    render();
  } catch (error) {
    el.muxStatus.classList.remove('online');
    if (!String(error.message).includes('CEO token required')) notify(error.message, true);
  } finally {
    state.refreshing = false;
  }
}

function render() {
  renderRoster();
  renderProposals();
  renderInspector();
  syncOffice();
}

function renderRoster() {
  el.roster.replaceChildren();
  el.emptyRoster.classList.toggle('hidden', state.employees.length > 0);
  for (const employee of state.employees) {
    const card = document.createElement('button');
    card.className = `employee-card${employee.id === state.selectedId ? ' selected' : ''}`;
    card.type = 'button';
    card.dataset.employeeId = employee.id;

    const avatar = document.createElement('span');
    avatar.className = `avatar ${employee.status}`;
    avatar.textContent = initials(employee.name);
    const copy = document.createElement('span');
    copy.className = 'employee-copy';
    const name = document.createElement('strong');
    name.textContent = employee.name;
    const role = document.createElement('span');
    role.textContent = employee.role;
    copy.append(name, role);
    const badge = document.createElement('span');
    badge.className = 'employee-state';
    badge.textContent = employee.status;
    card.append(avatar, copy, badge);
    card.addEventListener('click', () => selectEmployee(employee.id));
    el.roster.append(card);
  }
}

function renderProposals() {
  const pending = state.proposals.filter((proposal) => proposal.status === 'pending');
  el.proposalCount.textContent = String(pending.length);
  el.proposals.replaceChildren();
  for (const proposal of pending) {
    const card = document.createElement('div');
    card.className = 'proposal';
    const title = document.createElement('strong');
    title.textContent = `${proposal.kind.toUpperCase()} · ${proposal.title}`;
    const source = document.createElement('p');
    source.textContent = `Proposed by ${proposal.employee_name}`;
    const actions = document.createElement('div');
    actions.className = 'proposal-actions';
    const reject = document.createElement('button');
    reject.className = 'danger';
    reject.textContent = 'Reject';
    const approve = document.createElement('button');
    approve.className = 'primary';
    approve.textContent = 'Approve';
    reject.addEventListener('click', () => decideProposal(proposal.id, false));
    approve.addEventListener('click', () => decideProposal(proposal.id, true));
    actions.append(reject, approve);
    card.append(title, source, actions);
    el.proposals.append(card);
  }
}

function renderInspector() {
  const employee = selectedEmployee();
  el.placeholder.classList.toggle('hidden', Boolean(employee));
  el.detail.classList.toggle('hidden', !employee);
  if (!employee) return;
  $('#profile-avatar').textContent = initials(employee.name);
  $('#profile-name').textContent = employee.name;
  $('#profile-role').textContent = employee.role;
  $('#profile-state').textContent = employee.status;
  $('#profile-mux').textContent = employee.mux_name;
  $('#profile-mux').title = employee.mux_name;
  $('#profile-workspace').textContent = shortPath(employee.workspace);
  $('#profile-workspace').title = employee.workspace;
  const profile = employee.profile || {};
  $('#profile-voice').textContent = `${profile.voice || 'Unassigned'} voice`;
  $('#voice-accent').style.background = profile.accent || '#8290a7';
  $('#voice-accent').style.color = profile.accent || '#8290a7';
  $('#profile-temperament').textContent = profile.temperament || '';
  $('#profile-cadence').textContent = profile.cadence || '';
  $('#profile-model').textContent = profile.live_model || '';
  $('#task-state').textContent = employee.status;
  $('#terminal-output').textContent = employee.output_tail || 'Waiting for an assignment.';
  $('#terminal-output').scrollTop = $('#terminal-output').scrollHeight;
  $('#assign-button').disabled = employee.status === 'working';
}

function selectEmployee(employeeId) {
  state.selectedId = employeeId;
  renderRoster();
  renderInspector();
  const avatar = state.avatars.get(employeeId);
  if (avatar) {
    const target = avatar.group.position.clone();
    target.y = 1.2;
    controls.target.lerp(target, 0.8);
  }
}

async function decideProposal(proposalId, approve) {
  try {
    await api(`/api/proposals/${proposalId}/decision`, {
      method: 'POST', body: JSON.stringify({ approve }),
    });
    notify(approve ? 'Proposal approved' : 'Proposal rejected');
    await refresh();
  } catch (error) { notify(error.message, true); }
}

// ---- 3D office -----------------------------------------------------------
const container = $('#office-canvas');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07111e);
scene.fog = new THREE.FogExp2(0x07111e, 0.026);
const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 120);
camera.position.set(11, 13, 17);
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.8));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI / 2.12;
controls.minDistance = 7;
controls.maxDistance = 32;
controls.target.set(0, 0.5, 0);

scene.add(new THREE.HemisphereLight(0x9fdcff, 0x101622, 2.2));
const keyLight = new THREE.DirectionalLight(0xd6f6ff, 3.2);
keyLight.position.set(-6, 14, 8);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
scene.add(keyLight);
const cyanLight = new THREE.PointLight(0x42e8d5, 12, 18);
cyanLight.position.set(6, 5, -5);
scene.add(cyanLight);
const violetLight = new THREE.PointLight(0x8174ff, 9, 16);
violetLight.position.set(-7, 4, 2);
scene.add(violetLight);

const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(30, 20),
  new THREE.MeshStandardMaterial({ color: 0x0b1725, roughness: 0.8, metalness: 0.15 }),
);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);
const grid = new THREE.GridHelper(30, 30, 0x1d5660, 0x16293a);
grid.position.y = 0.008;
grid.material.opacity = 0.35;
grid.material.transparent = true;
scene.add(grid);

const wallMaterial = new THREE.MeshStandardMaterial({ color: 0x0c1929, roughness: 0.82 });
const rearWall = new THREE.Mesh(new THREE.BoxGeometry(30, 7, .2), wallMaterial);
rearWall.position.set(0, 3.5, -10);
rearWall.receiveShadow = true;
scene.add(rearWall);

function addMeetingTable() {
  const table = new THREE.Mesh(
    new THREE.CylinderGeometry(2.5, 2.5, .28, 48),
    new THREE.MeshStandardMaterial({ color: 0x27364d, roughness: .35, metalness: .45 }),
  );
  table.position.set(5.8, 1, -4.8);
  table.castShadow = true;
  scene.add(table);
  for (let i = 0; i < 6; i += 1) {
    const chair = new THREE.Mesh(
      new THREE.BoxGeometry(.7, .75, .65),
      new THREE.MeshStandardMaterial({ color: 0x122235, roughness: .75 }),
    );
    const angle = (i / 6) * Math.PI * 2;
    chair.position.set(5.8 + Math.cos(angle) * 3.3, .52, -4.8 + Math.sin(angle) * 3.3);
    chair.rotation.y = -angle + Math.PI / 2;
    scene.add(chair);
  }
}
addMeetingTable();

const employeeLayer = new THREE.Group();
scene.add(employeeLayer);

function statusColor(status) {
  return {
    working: 0x42e8d5,
    review: 0xffc857,
    blocked: 0xff6b81,
    offline: 0x667085,
  }[status] || 0x8290a7;
}

function makeLabel(text) {
  const canvas = document.createElement('canvas');
  canvas.width = 512; canvas.height = 128;
  const context = canvas.getContext('2d');
  context.fillStyle = 'rgba(4,10,18,.82)';
  context.roundRect(4, 4, 504, 120, 24); context.fill();
  context.strokeStyle = 'rgba(120,180,200,.38)'; context.lineWidth = 3; context.stroke();
  context.fillStyle = '#eaf6ff'; context.font = '700 36px sans-serif';
  context.textAlign = 'center'; context.textBaseline = 'middle';
  context.fillText(text.slice(0, 24), 256, 64);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
  sprite.scale.set(3.2, .8, 1);
  sprite.position.y = 3.4;
  return sprite;
}

function createDesk(position) {
  const group = new THREE.Group();
  const top = new THREE.Mesh(
    new THREE.BoxGeometry(3.1, .18, 1.45),
    new THREE.MeshStandardMaterial({ color: 0x25364a, roughness: .42, metalness: .32 }),
  );
  top.position.y = 1.05; top.castShadow = true; group.add(top);
  const monitor = new THREE.Mesh(
    new THREE.BoxGeometry(1.25, .8, .08),
    new THREE.MeshStandardMaterial({ color: 0x071018, emissive: 0x123f46, emissiveIntensity: .7 }),
  );
  monitor.position.set(0, 1.65, -.25); monitor.rotation.x = -.08; group.add(monitor);
  for (const x of [-1.25, 1.25]) {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(.12, 1.05, .12), new THREE.MeshStandardMaterial({ color: 0x35465b }));
    leg.position.set(x, .52, 0); group.add(leg);
  }
  group.position.copy(position);
  return group;
}

function createAvatar(employee, index) {
  const group = new THREE.Group();
  const color = new THREE.Color().setHSL(((index * .19) + .48) % 1, .58, .58);
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(.38, .8, 5, 12),
    new THREE.MeshStandardMaterial({ color, roughness: .55 }),
  );
  body.position.y = 1.75; body.castShadow = true; group.add(body);
  const head = new THREE.Mesh(
    new THREE.SphereGeometry(.38, 24, 16),
    new THREE.MeshStandardMaterial({ color: 0xd7a77d, roughness: .7 }),
  );
  head.position.y = 2.7; head.castShadow = true; group.add(head);
  const ringMaterial = new THREE.MeshBasicMaterial({ color: statusColor(employee.status), transparent: true, opacity: .75 });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(.72, .045, 10, 42), ringMaterial);
  ring.rotation.x = Math.PI / 2; ring.position.y = .05; group.add(ring);
  group.add(makeLabel(employee.name));
  group.traverse((object) => { object.userData.employeeId = employee.id; });
  return { group, body, head, ring, desk: null, phase: index * 1.7 };
}

function employeePosition(index) {
  const column = index % 3;
  const row = Math.floor(index / 3);
  return new THREE.Vector3(-6.2 + column * 4.6, 0, 4.1 - row * 4.5);
}

function syncOffice() {
  for (const [id, avatar] of state.avatars) {
    if (!state.employees.some((employee) => employee.id === id)) {
      employeeLayer.remove(avatar.group, avatar.desk);
      state.avatars.delete(id);
    }
  }
  state.employees.forEach((employee, index) => {
    let avatar = state.avatars.get(employee.id);
    if (!avatar) {
      avatar = createAvatar(employee, index);
      avatar.desk = createDesk(employeePosition(index));
      avatar.group.position.copy(employeePosition(index)).add(new THREE.Vector3(0, 0, .65));
      employeeLayer.add(avatar.desk, avatar.group);
      state.avatars.set(employee.id, avatar);
    }
    avatar.ring.material.color.setHex(statusColor(employee.status));
    avatar.employee = employee;
  });
}

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener('pointerdown', (event) => {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects([...state.avatars.values()].map((value) => value.group), true)[0];
  if (hit?.object.userData.employeeId) selectEmployee(hit.object.userData.employeeId);
});

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const time = clock.getElapsedTime();
  for (const [id, avatar] of state.avatars) {
    const working = avatar.employee?.status === 'working';
    const speaking = state.speaking.has(`employee:${id}`);
    avatar.body.rotation.z = working ? Math.sin(time * 8 + avatar.phase) * .025 : 0;
    avatar.head.rotation.y = Math.sin(time * (speaking ? 6 : 1.3) + avatar.phase) * (speaking ? .16 : .05);
    avatar.ring.scale.setScalar(speaking ? 1 + Math.sin(time * 9) * .13 : 1);
    avatar.ring.material.opacity = working || speaking ? .95 : .48;
  }
  controls.update();
  renderer.render(scene, camera);
}

function resize() {
  const { clientWidth, clientHeight } = container;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / Math.max(clientHeight, 1);
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize(); animate();

// ---- LiveKit media -------------------------------------------------------
function mediaTile(participant) {
  let tile = document.querySelector(`[data-participant="${CSS.escape(participant.identity)}"]`);
  if (!tile) {
    tile = document.createElement('div'); tile.className = 'video-tile';
    tile.dataset.participant = participant.identity;
    const label = document.createElement('span');
    label.textContent = participant.name || participant.identity;
    tile.append(label); el.videoStage.append(tile);
  }
  return tile;
}

function attachTrack(track, participant) {
  const element = track.attach();
  element.autoplay = true; element.playsInline = true;
  if (track.kind === Track.Kind.Video) mediaTile(participant).prepend(element);
  else el.audioStage.append(element);
}

async function connectRoom(tokenPath, kind) {
  if (state.room) await leaveRoom();
  const credentials = await api(tokenPath, { method: 'POST', body: JSON.stringify({ name: 'CEO' }) });
  const room = new Room({ adaptiveStream: true, dynacast: true });
  room.on(RoomEvent.TrackSubscribed, attachTrack);
  room.on(RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((node) => node.remove()));
  room.on(RoomEvent.ParticipantDisconnected, (participant) => {
    document.querySelector(`[data-participant="${CSS.escape(participant.identity)}"]`)?.remove();
  });
  room.on(RoomEvent.ActiveSpeakersChanged, (participants) => {
    state.speaking = new Set(participants.map((participant) => participant.identity));
  });
  room.on(RoomEvent.Disconnected, () => { if (state.room === room) resetMediaUi(); });
  await room.connect(credentials.url, credentials.token);
  await room.startAudio();
  state.room = room; state.roomKind = kind;
  el.livekitStatus.classList.add('online');
  el.officeButton.classList.add('hidden'); el.leaveButton.classList.remove('hidden');
  el.micButton.disabled = false; el.cameraButton.disabled = false;
  el.meetingLabel.textContent = kind === 'office' ? 'Inside the live office' : `Private meeting with ${selectedEmployee()?.name || 'employee'}`;
  el.meetingRoom.textContent = credentials.room;
  try {
    await room.localParticipant.setMicrophoneEnabled(true);
    el.micButton.classList.add('active');
  } catch (error) { notify(`Microphone: ${error.message}`, true); }
  try {
    await room.localParticipant.setCameraEnabled(true);
    el.cameraButton.classList.add('active');
  } catch (error) { notify(`Camera: ${error.message}`, true); }
  notify(`Connected to ${kind === 'office' ? 'the office' : 'private meeting'}`);
}

function resetMediaUi() {
  state.room = null; state.roomKind = null; state.speaking.clear();
  el.videoStage.replaceChildren(); el.audioStage.replaceChildren();
  el.livekitStatus.classList.remove('online');
  el.officeButton.classList.remove('hidden'); el.leaveButton.classList.add('hidden');
  el.micButton.disabled = true; el.cameraButton.disabled = true;
  el.micButton.classList.remove('active'); el.cameraButton.classList.remove('active');
  el.meetingLabel.textContent = 'Office audio is off';
  el.meetingRoom.textContent = 'Connect to speak with the team';
}

async function leaveRoom() {
  const room = state.room;
  resetMediaUi();
  if (room) await room.disconnect();
}

el.officeButton.addEventListener('click', () => connectRoom('/api/office-token', 'office').catch((error) => notify(error.message, true)));
el.leaveButton.addEventListener('click', () => leaveRoom());
el.micButton.addEventListener('click', async () => {
  if (!state.room) return;
  const enabled = !state.room.localParticipant.isMicrophoneEnabled;
  await state.room.localParticipant.setMicrophoneEnabled(enabled);
  el.micButton.classList.toggle('active', enabled);
});
el.cameraButton.addEventListener('click', async () => {
  if (!state.room) return;
  const enabled = !state.room.localParticipant.isCameraEnabled;
  await state.room.localParticipant.setCameraEnabled(enabled);
  el.cameraButton.classList.toggle('active', enabled);
});

// ---- Product interactions ------------------------------------------------
$('#hire-open').addEventListener('click', () => $('#hire-dialog').showModal());
document.querySelectorAll('[data-close]').forEach((button) => button.addEventListener('click', () => $('#hire-dialog').close()));
$('#hire-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const employee = await api('/api/employees', { method: 'POST', body: JSON.stringify(values) });
    $('#hire-dialog').close(); event.currentTarget.reset();
    state.selectedId = employee.id;
    notify(`${employee.name} hired — mux ${employee.mux_name} is live`);
    await refresh();
  } catch (error) { notify(error.message, true); }
});

$('#assign-button').addEventListener('click', async () => {
  const employee = selectedEmployee();
  const objective = $('#task-objective').value.trim();
  if (!employee || !objective) return notify('Write an objective first', true);
  try {
    await api(`/api/employees/${employee.id}/tasks`, {
      method: 'POST', body: JSON.stringify({ objective, source: 'ceo' }),
    });
    $('#task-objective').value = '';
    notify(`${employee.name} started working inside ${employee.mux_name}`);
    await refresh();
  } catch (error) { notify(error.message, true); }
});

$('#private-meeting-button').addEventListener('click', () => {
  const employee = selectedEmployee();
  if (!employee) return;
  connectRoom(`/api/employees/${employee.id}/meeting-token`, 'private').catch((error) => notify(error.message, true));
});

$('#auth-button').addEventListener('click', () => {
  const token = window.prompt('CEO access token (stored only for this browser tab):', ceoToken());
  if (token === null) return;
  if (token.trim()) sessionStorage.setItem('remoteEmployeeToken', token.trim());
  else sessionStorage.removeItem('remoteEmployeeToken');
  refresh();
});

async function boot() {
  try {
    const config = await api('/api/config');
    el.livekitStatus.classList.toggle('warning', !config.livekit_configured);
    if (config.auth_required && !ceoToken()) {
      const token = window.prompt('Enter the Remote Employee CEO token:');
      if (token) sessionStorage.setItem('remoteEmployeeToken', token);
    }
  } catch (error) { notify(error.message, true); }
  await refresh();
  setInterval(refresh, 2000);
}

boot();