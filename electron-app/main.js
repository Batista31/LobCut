const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const { composeStop, composeUp, logFile } = require('./lib/docker');
const { pollHealth } = require('./lib/poller');

const projectRoot = path.join(__dirname, '..');
const dashboardDistPath = path.join(projectRoot, 'dashboard', 'dist', 'index.html');
const desktopFallbackPath = path.join(__dirname, 'desktop.html');
const healthUrl = 'http://localhost:8000/health';
const dashboardUrl = process.env.LOBCUT_DASHBOARD_URL || '';
const skipDocker = process.env.LOBCUT_SKIP_DOCKER === '1';

let splashWindow = null;
let mainWindow = null;
let mainWindowReady = null;
let stopping = false;

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
    mainWindowReady = mainWindow.loadURL(dashboardUrl);
    return mainWindow;
  }
  const dashboardPath = require('fs').existsSync(dashboardDistPath)
    ? dashboardDistPath
    : desktopFallbackPath;
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
  mainWindow.show();

  if (!dashboardUrl && !require('fs').existsSync(dashboardDistPath)) {
    await injectHealthBanner('Using Electron fallback dashboard because dashboard/dist was not found.');
  }

  if (!health.ok) {
    await injectHealthBanner(`LobCut backend is not responding: ${health.error}`);
  }
}

async function stopServices() {
  if (stopping) return;
  stopping = true;
  if (skipDocker) return;
  await composeStop(projectRoot);
}

ipcMain.handle('app:get-version', () => app.getVersion());

app.whenReady().then(() => {
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
