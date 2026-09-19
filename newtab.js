const dock = document.getElementById('dock');
const clockH = document.getElementById('clockH');
const clockM = document.getElementById('clockM');
const clockS = document.getElementById('clockS');
const clockDate = document.getElementById('clockDate');
const addPanel = document.getElementById('addPanel');
const addName = document.getElementById('addName');
const addUrl = document.getElementById('addUrl');

const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function ordinal(n) {
  if (n % 10 === 1 && n % 100 !== 11) return n + 'st';
  if (n % 10 === 2 && n % 100 !== 12) return n + 'nd';
  if (n % 10 === 3 && n % 100 !== 13) return n + 'rd';
  return n + 'th';
}

// Hand-picked high-res icons for sites where the live fetch chain below
// falls short (wrong style, or the site just doesn't serve a good one at a
// guessable path). Add more here as needed: drop a PNG in icons/apps/ and
// add a matching hostname keyword.
const CURATED_ICONS = {
  whatsapp: 'icons/apps/whatsapp.png',
  youtube: 'icons/apps/youtube.png',
};

function curatedIcon(pageUrl) {
  const host = new URL(pageUrl).hostname;
  for (const [keyword, path] of Object.entries(CURATED_ICONS)) {
    if (host.includes(keyword)) return chrome.runtime.getURL(path);
  }
  return null;
}

function iconCandidates(pageUrl) {
  const curated = curatedIcon(pageUrl);
  if (curated) return [curated];

  // High-res icons straight from the site itself, no third party involved.
  // apple-touch-icon is the closest thing to a standard "app icon" format:
  // square, high-res, deliberately designed -- exactly the iOS look asked for.
  const origin = new URL(pageUrl).origin;
  return [
    `${origin}/apple-touch-icon.png`,
    `${origin}/apple-touch-icon-precomposed.png`,
    `${origin}/favicon.ico`,
  ];
}

function loadBestIcon(img, letter, candidates, i = 0) {
  if (i >= candidates.length) {
    img.remove();
    return;
  }
  img.onerror = () => loadBestIcon(img, letter, candidates, i + 1);
  img.onload = () => letter.remove();
  img.src = candidates[i];
}

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}

function chroma(hex) {
  const [r, g, b] = hexToRgb(hex);
  return Math.max(r, g, b) - Math.min(r, g, b);
}

async function applyColors() {
  try {
    const res = await fetch(chrome.runtime.getURL('colors.json') + '?t=' + Date.now());
    const c = await res.json();
    const root = document.documentElement.style;
    root.setProperty('--background', c.background);
    root.setProperty('--surface', c.surface);
    root.setProperty('--surface-variant', c.surface_variant);
    root.setProperty('--on-surface', c.on_surface);
    root.setProperty('--on-surface-variant', c.on_surface_variant);
    root.setProperty('--outline-variant', c.outline_variant);
    root.setProperty('--primary', c.primary);
    root.setProperty('--on-primary', c.on_primary);

    // On a near-monochrome wallpaper, matugen's primary can collapse to an
    // essentially colorless near-white -- indistinguishable from on-surface.
    // Detect that directly (low R/G/B spread) rather than comparing to
    // on-surface, and fall back to on-surface-variant, a real distinguishable
    // grey, so the accent digits stay visible either way.
    const accent = chroma(c.primary) < 20 ? c.on_surface_variant : c.primary;
    root.setProperty('--accent', accent);
  } catch (e) {
    // colors.json missing/invalid: fall back to the defaults baked into newtab.css
  }
}

let lastDate = null;

function tickClock() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  clockH.textContent = pad(now.getHours());
  clockM.textContent = pad(now.getMinutes());
  clockS.textContent = pad(now.getSeconds());

  const dayKey = now.toDateString();
  if (dayKey !== lastDate) {
    lastDate = dayKey;
    clockDate.innerHTML = `${DAY_NAMES[now.getDay()]} <span class="accent">${ordinal(now.getDate())} ${MONTH_NAMES[now.getMonth()]}</span>`;
  }
}

function normalizeUrl(raw) {
  const trimmed = raw.trim();
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return 'https://' + trimmed;
}

async function getLinks() {
  const { links } = await chrome.storage.local.get('links');
  return links || [];
}

async function saveLinks(links) {
  await chrome.storage.local.set({ links });
}

function makeDockItem(link, index) {
  const a = document.createElement('a');
  a.className = 'dock-item';
  a.href = link.url;
  a.dataset.name = link.name;

  const letter = document.createElement('div');
  letter.className = 'letter';
  letter.textContent = link.name.trim().charAt(0) || '?';
  a.appendChild(letter);

  const icon = document.createElement('img');
  icon.alt = '';
  a.appendChild(icon);
  loadBestIcon(icon, letter, iconCandidates(link.url));

  const remove = document.createElement('button');
  remove.className = 'remove';
  remove.textContent = '×';
  remove.title = 'Remove';
  remove.addEventListener('click', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const links = await getLinks();
    links.splice(index, 1);
    await saveLinks(links);
    render();
  });
  a.appendChild(remove);

  return a;
}

function makeAddItem() {
  const div = document.createElement('div');
  div.className = 'dock-item add';
  const plus = document.createElement('div');
  plus.className = 'plus';
  plus.textContent = '+';
  div.appendChild(plus);
  div.addEventListener('click', openAddPanel);
  return div;
}

function openAddPanel() {
  addPanel.hidden = false;
  addName.value = '';
  addUrl.value = '';
  addName.focus();
}

function closeAddPanel() {
  addPanel.hidden = true;
}

async function submitAdd() {
  const name = addName.value.trim();
  const url = addUrl.value.trim();
  if (!name || !url) return;
  const links = await getLinks();
  links.push({ name, url: normalizeUrl(url) });
  await saveLinks(links);
  closeAddPanel();
  render();
}

async function render() {
  const links = await getLinks();
  dock.innerHTML = '';
  links.forEach((link, i) => dock.appendChild(makeDockItem(link, i)));
  if (links.length) {
    const divider = document.createElement('div');
    divider.className = 'dock-divider';
    dock.appendChild(divider);
  }
  dock.appendChild(makeAddItem());
}

document.getElementById('addCancel').addEventListener('click', closeAddPanel);
document.getElementById('addSave').addEventListener('click', submitAdd);
addPanel.addEventListener('click', (e) => { if (e.target === addPanel) closeAddPanel(); });
[addName, addUrl].forEach((input) => {
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitAdd();
    if (e.key === 'Escape') closeAddPanel();
  });
});

applyColors();
setInterval(applyColors, 1000);
tickClock();
setInterval(tickClock, 1000);
render();
