const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('lobcut', {
  getVersion: () => ipcRenderer.invoke('app:get-version'),
  openOutputFolder: (filePath) => ipcRenderer.send('open-output-folder', filePath),
  onDockerStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('docker:status', listener);
    return () => ipcRenderer.removeListener('docker:status', listener);
  },
});

contextBridge.exposeInMainWorld('watcherAPI', {
  add: (path) => ipcRenderer.invoke('watcher:add', path),
  remove: (id, path) => ipcRenderer.invoke('watcher:remove', id, path),
  toggle: (id, path, enabled) => ipcRenderer.invoke('watcher:toggle', id, path, enabled),
});
