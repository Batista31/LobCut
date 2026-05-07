const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const dns = require('dns');
const fs = require('fs');
const path = require('path');
const chokidar = require('chokidar');
const { composeStop, composeUp, logFile } = require('./lib/docker');
const { pollHealth } = require('./lib/poller');

const projectRoot = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
const dashboardDistPath = path.join(projectRoot, 'dashboard', 'dist', 'index.html');
const dashboardPublicPath = path.join(projectRoot, 'dashboard', 'public');
const desktopFallbackPath = path.join(__dirname, 'desktop.html');
const healthUrl = 'http://localhost:8000/health';
const dashboardUrl = process.env.LOBCUT_USE_REMOTE_DASHBOARD === '1'
  ? (process.env.LOBCUT_DASHBOARD_URL || '')
  : '';
const skipDocker = process.env.LOBCUT_SKIP_DOCKER === '1';
const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.heic'];
const VIDEO_EXTS = ['.mp4', '.mov', '.avi', '.mkv', '.webm'];
const INPUT_IMAGES = path.join(projectRoot, 'input', 'images');
const INPUT_VIDEOS = path.join(projectRoot, 'input', 'videos');

let splashWindow = null;
let mainWindow = null;
let mainWindowReady = null;
let stopping = false;
let activeWatchers = {};

dns.setDefaultResultOrder('ipv4first');

function copyDashboardAssets() {
  try {
    const assets = [
      { src: path.join(projectRoot, 'LobCut mark.jpeg'), filename: 'lobcut-mark.jpeg' },
      { src: path.join(projectRoot, 'LobCut mark.png'), filename: 'lobcut-mark.png' },
      { src: path.join(projectRoot, 'LobCut telegram.png'), filename: 'lobcut-telegram.png' },
    ];
    const assetDirs = [
      dashboardPublicPath,
      path.join(projectRoot, 'dashboard', 'dist'),
    ];

    for (const asset of assets) {
      if (!fs.existsSync(asset.src)) continue;
      for (const assetDir of assetDirs) {
        const assetDest = path.join(assetDir, asset.filename);
        fs.mkdirSync(path.dirname(assetDest), { recursive: true });
        fs.copyFileSync(asset.src, assetDest);
      }
    }
  } catch (error) {
    console.warn('[Assets] Could not copy LobCut dashboard assets:', error.message);
  }
}

function sendDockerStatus(status) {
  for (const window of BrowserWindow.getAllWindows()) {
    window.webContents.send('docker:status', status);
  }
}

function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 520,
    height: 360,
    resizable: false,
    show: true,
    backgroundColor: '#0f0f0f',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    backgroundColor: '#0e0e10',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (dashboardUrl) {
    console.log(`[Dashboard] Loading remote dashboard: ${dashboardUrl}`);
    mainWindowReady = mainWindow.loadURL(dashboardUrl);
    return mainWindow;
  }
  const dashboardPath = require('fs').existsSync(dashboardDistPath)
    ? dashboardDistPath
    : desktopFallbackPath;
  console.log(`[Dashboard] Loading local dashboard: ${dashboardPath}`);
  mainWindowReady = mainWindow.loadFile(dashboardPath);
  return mainWindow;
}

async function showDockerError(error) {
  const result = await dialog.showMessageBox({
    type: 'error',
    buttons: ['Open Docker Download', 'Continue Anyway'],
    defaultId: 0,
    cancelId: 1,
    title: 'Docker is not available',
    message: 'LobCut could not start Docker Compose services.',
    detail: `${error.message}\n\nDocker output is logged at:\n${logFile}`,
  });
  if (result.response === 0) {
    await shell.openExternal('https://docs.docker.com/get-docker/');
  }
}

async function injectHealthBanner(message) {
  if (!mainWindow) return;
  const safeMessage = JSON.stringify(message);
  await mainWindow.webContents.executeJavaScript(`
    (() => {
      const banner = document.createElement('div');
      banner.textContent = ${safeMessage};
      banner.style.position = 'fixed';
      banner.style.top = '0';
      banner.style.left = '0';
      banner.style.right = '0';
      banner.style.zIndex = '99999';
      banner.style.padding = '12px 16px';
      banner.style.background = '#7f1d1d';
      banner.style.color = '#fff';
      banner.style.fontFamily = 'system-ui, sans-serif';
      banner.style.fontSize = '14px';
      document.body.appendChild(banner);
    })();
  `);
}

async function injectTelegramQrHelp() {
  if (!mainWindow || mainWindow.isDestroyed()) return;

  let qrDataUrl = '';
  try {
    const qrPath = path.join(projectRoot, 'dashboard', 'dist', 'lobcut-telegram.png');
    if (fs.existsSync(qrPath)) {
      qrDataUrl = `data:image/png;base64,${fs.readFileSync(qrPath).toString('base64')}`;
    }
  } catch (error) {
    console.warn('[Telegram QR] Could not read QR image:', error.message);
  }
  if (!qrDataUrl) return;

  const safeQrDataUrl = JSON.stringify(qrDataUrl);
  await mainWindow.webContents.executeJavaScript(`
    (() => {
      const QR_DATA_URL = ${safeQrDataUrl};
      const STYLE_ID = 'lobcut-telegram-qr-style';
      const BLOCK_ID = 'lobcut-telegram-qr-help';

      function ensureStyle() {
        if (document.getElementById(STYLE_ID)) return;
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = \`
          #\${BLOCK_ID} {
            display: grid;
            grid-template-columns: 132px minmax(0, 1fr);
            gap: 18px;
            align-items: start;
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid rgba(148, 163, 184, 0.16);
            color: #9ca3af;
            font: 13px/1.5 Inter, system-ui, sans-serif;
          }
          #\${BLOCK_ID} img {
            width: 120px;
            height: 120px;
            object-fit: contain;
            border-radius: 6px;
            border: 1px solid rgba(148, 163, 184, 0.24);
            background: #fff;
            padding: 6px;
          }
          #\${BLOCK_ID} strong {
            display: block;
            color: #f3f4f6;
            font-size: 14px;
            margin-bottom: 6px;
          }
          #\${BLOCK_ID} ol {
            margin: 0;
            padding-left: 18px;
          }
          #\${BLOCK_ID} p {
            margin: 8px 0 0;
          }
        \`;
        document.head.appendChild(style);
      }

      function findTelegramCard() {
        const candidates = Array.from(document.querySelectorAll('article, section, div'))
          .filter((el) => el.textContent && el.textContent.includes('Telegram Notifications') && el.querySelector('input'))
          .sort((a, b) => a.textContent.length - b.textContent.length);
        return candidates[0] || null;
      }

      function inject() {
        const card = findTelegramCard();
        if (!card || card.querySelector('#' + BLOCK_ID)) return;
        ensureStyle();

        const block = document.createElement('div');
        block.id = BLOCK_ID;
        block.innerHTML = \`
          <div>
            <img src="\${QR_DATA_URL}" alt="LobCut Telegram bot QR code" />
          </div>
          <div>
            <strong>How to link Telegram</strong>
            <ol>
              <li>Scan this QR or open the LobCut bot in Telegram.</li>
              <li>Send <code>/start</code> to the LobCut bot.</li>
              <li>Open <code>@userinfobot</code> and send <code>/start</code>.</li>
              <li>Copy only the numeric ID it replies with, like <code>1179051234</code>.</li>
              <li>Paste that number here, click Link or Save, then Test.</li>
            </ol>
            <p>This is not your phone number. Telegram requires you to start the LobCut bot once before private notifications can work.</p>
          </div>
        \`;

        const oldHint = Array.from(card.querySelectorAll('p')).find((p) =>
          p.textContent && p.textContent.toLowerCase().includes('message your bot first')
        );
        if (oldHint) {
          oldHint.replaceWith(block);
        } else {
          card.appendChild(block);
        }
      }

      inject();
      if (!window.__lobcutTelegramQrObserver) {
        window.__lobcutTelegramQrObserver = new MutationObserver(inject);
        window.__lobcutTelegramQrObserver.observe(document.body, { childList: true, subtree: true });
      }
    })();
  `);
}

async function startServicesAndShowWindow() {
  sendDockerStatus('starting');
  if (!skipDocker) {
    try {
      await composeUp(projectRoot);
    } catch (error) {
      sendDockerStatus('error');
      await showDockerError(error);
    }
  }

  const health = await pollHealth(healthUrl, { intervalMs: 2000, timeoutMs: 30000 });
  if (health.ok) {
    sendDockerStatus('ready');
  } else {
    sendDockerStatus('error');
  }

  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.close();
  }
  await mainWindowReady;
  await injectTelegramQrHelp();
  mainWindow.show();

  if (!dashboardUrl && !require('fs').existsSync(dashboardDistPath)) {
    await injectHealthBanner('Using Electron fallback dashboard because dashboard/dist was not found.');
  }

  if (!health.ok) {
    await injectHealthBanner(`LobCut backend is not responding: ${health.error}`);
  } else {
    await initWatchers();
  }
  await injectTelegramQrHelp();
}

async function stopServices() {
  if (stopping) return;
  stopping = true;
  await stopAllWatchers();
  if (skipDocker) return;
  await composeStop(projectRoot);
}

function ensureInputFolders() {
  fs.mkdirSync(INPUT_IMAGES, { recursive: true });
  fs.mkdirSync(INPUT_VIDEOS, { recursive: true });
}

function startWatcher(folderPath) {
  if (!folderPath || activeWatchers[folderPath]) return;
  ensureInputFolders();
  const watcher = chokidar.watch(folderPath, {
    persistent: true,
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 2000, pollInterval: 500 },
  });
  watcher.on('add', (filePath) => {
    const ext = path.extname(filePath).toLowerCase();
    let dest = null;
    if (IMAGE_EXTS.includes(ext)) dest = INPUT_IMAGES;
    else if (VIDEO_EXTS.includes(ext)) dest = INPUT_VIDEOS;
    if (!dest) return;

    const destFile = path.join(dest, path.basename(filePath));
    if (path.resolve(filePath) === path.resolve(destFile)) return;
    fs.copyFile(filePath, destFile, (err) => {
      if (err) console.error('[Watcher] Copy failed:', err);
      else console.log(`[Watcher] Copied ${filePath} -> ${destFile}`);
    });
  });
  watcher.on('error', (error) => console.error('[Watcher] Error:', error));
  activeWatchers[folderPath] = watcher;
  console.log(`[Watcher] Started watching: ${folderPath}`);
}

function stopWatcher(folderPath) {
  if (!folderPath || !activeWatchers[folderPath]) return;
  activeWatchers[folderPath].close();
  delete activeWatchers[folderPath];
  console.log(`[Watcher] Stopped: ${folderPath}`);
}

async function stopAllWatchers() {
  const watchers = Object.values(activeWatchers);
  activeWatchers = {};
  await Promise.all(watchers.map((watcher) => watcher.close()));
}

async function initWatchers() {
  try {
    const res = await fetch('http://localhost:8000/watchers');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const folders = await res.json();
    folders.filter((f) => f.enabled).forEach((f) => startWatcher(f.path));
  } catch (error) {
    console.error('[Watcher] Could not load watchers from API:', error.message);
  }
}

ipcMain.handle('app:get-version', () => app.getVersion());

ipcMain.handle('watcher:add', async (_event, folderPath) => {
  const res = await fetch('http://localhost:8000/watchers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: folderPath, enabled: true }),
  });
  if (!res.ok) throw new Error(await res.text());
  const watcher = await res.json();
  startWatcher(folderPath);
  return watcher;
});

ipcMain.handle('watcher:remove', async (_event, id, folderPath) => {
  const res = await fetch(`http://localhost:8000/watchers/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await res.text());
  stopWatcher(folderPath);
  return res.json();
});

ipcMain.handle('watcher:toggle', async (_event, id, folderPath, enabled) => {
  const res = await fetch(`http://localhost:8000/watchers/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(await res.text());
  const watcher = await res.json();
  if (enabled) startWatcher(folderPath);
  else stopWatcher(folderPath);
  return watcher;
});

ipcMain.on('open-output-folder', (_event, filePath) => {
  if (!filePath) return;

  const fs = require('fs');
  const normalized = String(filePath).replace(/\\/g, '/');
  const candidates = [
    filePath,
    normalized.replace(/^\/app\/python-service\/output\//, path.join(projectRoot, 'output').replace(/\\/g, '/') + '/'),
    normalized.replace(/^\/app\/output\//, path.join(projectRoot, 'output').replace(/\\/g, '/') + '/'),
    normalized.replace(/^\/app\/input\//, path.join(projectRoot, 'input').replace(/\\/g, '/') + '/'),
  ];

  const target = candidates.find((candidate) => fs.existsSync(candidate));
  if (target) {
    shell.showItemInFolder(target);
  } else {
    shell.openPath(path.join(projectRoot, 'output'));
  }
});

app.whenReady().then(() => {
  copyDashboardAssets();
  createSplashWindow();
  createMainWindow();
  startServicesAndShowWindow();
});

app.on('before-quit', (event) => {
  if (stopping) return;
  event.preventDefault();
  stopServices().finally(() => app.quit());
});

app.on('window-all-closed', () => {
  app.quit();
});
