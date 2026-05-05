const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('lobcut', {
  getVersion: () => ipcRenderer.invoke('app:get-version'),
  onDockerStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('docker:status', listener);
    return () => ipcRenderer.removeListener('docker:status', listener);
  },
});
