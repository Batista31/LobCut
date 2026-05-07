# Packaging LobCut for Windows

This builds the Electron desktop wrapper as a Windows NSIS installer.

## Prerequisites

- Node.js 20 or newer
- Docker Desktop installed on the target machine
- PowerShell or Command Prompt

## Build

From the repository root:

```powershell
cd D:\LobCut\electron-app
npm install
npm run build:win
```

The installer is written to:

```text
D:\LobCut\electron-app\dist\
```

For a folder build without an installer:

```powershell
cd D:\LobCut\electron-app
npm run pack:win
```

## Notes

- `build:win` builds `dashboard/dist` first, then packages Electron.
- The packaged app reads bundled resources from Electron's `resources` folder.
- `dashboard/dist` and `docker-compose.yml` are copied as packaged resources.
- The generated installer does not bundle Docker Desktop. Users still need Docker Desktop installed and running.

If the dashboard build fails with `spawn EPERM`, allow this file in Windows Security or run the build from a normal non-sandboxed terminal:

```text
D:\LobCut\dashboard\node_modules\@esbuild\win32-x64\esbuild.exe
```
