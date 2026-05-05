#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic"]);
const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".m4v"]);

async function readStdin() {
  if (process.stdin.isTTY) return "";
  return await new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { data += chunk; });
    process.stdin.on("end", () => resolve(data.trim()));
    process.stdin.on("error", reject);
  });
}

function parseInput(rawInput) {
  const fallback = process.argv[2] || process.env.FILE_PATH || "";
  if (!rawInput) return fallback;
  try {
    const parsed = JSON.parse(rawInput);
    if (typeof parsed === "string") return parsed;
    return parsed.file_path || parsed.filePath || parsed.path || parsed.input?.file_path || parsed.args?.file_path || fallback;
  } catch (_error) {
    return rawInput;
  }
}

function routeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) return "/process/image";
  if (VIDEO_EXTENSIONS.has(ext)) return "/process/video";
  throw new Error("Unsupported file type.");
}

async function main() {
  const filePath = path.resolve(String(parseInput(await readStdin()) || "").trim());
  if (!filePath) throw new Error("No file path provided.");
  if (!fs.existsSync(filePath)) throw new Error("File not found.");

  const baseUrl = (process.env.MEDIA_SERVICE_URL || "http://api:8000").replace(/\/+$/, "");
  const response = await fetch(`${baseUrl}${routeFor(filePath)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body));
  process.stdout.write(`${JSON.stringify(body, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
