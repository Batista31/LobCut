function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollHealth(url, options = {}) {
  const intervalMs = options.intervalMs || 2000;
  const timeoutMs = options.timeoutMs || 30000;
  const deadline = Date.now() + timeoutMs;
  let lastError = null;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.status === 200) {
        return { ok: true };
      }
      lastError = new Error(`Health returned HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await wait(intervalMs);
  }

  return {
    ok: false,
    error: lastError ? lastError.message : 'Health check timed out',
  };
}

module.exports = {
  pollHealth,
};
