const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const logDir = path.join(os.homedir(), 'lobcut-logs');
const logFile = path.join(logDir, 'docker.log');

function ensureLogDir() {
  fs.mkdirSync(logDir, { recursive: true });
}

function appendLog(message) {
  ensureLogDir();
  fs.appendFileSync(logFile, `[${new Date().toISOString()}] ${message}\n`);
}

function runCompose(projectRoot, args, options = {}) {
  return new Promise((resolve, reject) => {
    appendLog(`docker compose ${args.join(' ')}`);
    const child = spawn('docker', ['compose', ...args], {
      cwd: projectRoot,
      shell: process.platform === 'win32',
      env: process.env,
    });

    let output = '';

    child.stdout.on('data', (chunk) => {
      const text = chunk.toString();
      output += text;
      appendLog(text.trimEnd());
    });

    child.stderr.on('data', (chunk) => {
      const text = chunk.toString();
      output += text;
      appendLog(text.trimEnd());
    });

    child.on('error', (error) => {
      appendLog(`spawn error: ${error.message}`);
      reject(error);
    });

    child.on('close', (code) => {
      appendLog(`exit code: ${code}`);
      if (code === 0 || options.allowFailure) {
        resolve({ code, output });
      } else {
        const error = new Error(`docker compose ${args.join(' ')} failed with exit code ${code}`);
        error.output = output;
        reject(error);
      }
    });
  });
}

function composeUp(projectRoot) {
  return runCompose(projectRoot, ['up', '-d']);
}

function composeStop(projectRoot) {
  return runCompose(projectRoot, ['stop'], { allowFailure: true });
}

module.exports = {
  composeUp,
  composeStop,
  logFile,
};
