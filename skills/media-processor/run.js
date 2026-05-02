#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic"]);
const VIDEO_EXTENSIONS = new Set([".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv", ".m4v"]);

async function readStdin() {
  if (process.stdin.isTTY) {
    return "";
  }

  return await new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolve(data.trim()));
    process.stdin.on("error", reject);
  });
}

function parseContext(rawInput) {
  const argvPath = process.argv[2];
  const envPath = process.env.FILE_PATH;

  if (!rawInput) {
    return { file_path: argvPath || envPath || "" };
  }

  try {
    const parsed = JSON.parse(rawInput);
    if (typeof parsed === "string") {
      return { file_path: parsed };
    }
    if (parsed && typeof parsed === "object") {
      return {
        file_path:
          parsed.file_path ||
          parsed.filePath ||
          parsed.path ||
          parsed.input?.file_path ||
          parsed.args?.file_path ||
          argvPath ||
          envPath ||
          "",
      };
    }
  } catch (_error) {
    return { file_path: rawInput };
  }

  return { file_path: argvPath || envPath || "" };
}

function serviceBaseUrl() {
  return (process.env.MEDIA_SERVICE_URL || "http://localhost:8000").replace(/\/+$/, "");
}

function detectRoute(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) {
    return { route: "/process/image", type: "image" };
  }
  if (VIDEO_EXTENSIONS.has(ext)) {
    return { route: "/process/video", type: "video" };
  }
  return { route: null, type: null };
}

function formatImageResponse(result) {
  const tags = Array.isArray(result.tags) && result.tags.length ? result.tags.join(", ") : "none";
  const blurState = result.is_blurry ? "blurry" : "clear";
  const blurNote = result.is_blurry
    ? `\nWarning  : Image is blurry (score: ${Number(result.blur_score || 0).toFixed(2)}) - classification confidence may be reduced.`
    : "";
  const quotaNote = String(result.classifier || "").includes("fallback")
    ? "\nWarning  : Gemini quota hit - result used fallback classifier. Accuracy may be lower."
    : "";

  return [
    `Image processed: ${result.file}`,
    `Category  : ${result.category}`,
    `Tags      : ${tags}`,
    `Summary   : ${result.summary}`,
    `Blur      : ${Number(result.blur_score || 0).toFixed(2)} (${blurState})`,
    `Classifier: ${result.classifier}`,
    result.output_path ? `Output    : ${result.output_path}` : null,
    blurNote ? blurNote.trimEnd() : null,
    quotaNote ? quotaNote.trimEnd() : null,
  ]
    .filter(Boolean)
    .join("\n");
}

function formatVideoResponse(result) {
  const preview = (result.transcript || "").replace(/\s+/g, " ").trim();
  const transcriptPreview = preview.length > 200 ? `${preview.slice(0, 200).trimEnd()}...` : preview || "No transcript available.";

  return [
    `Video processed: ${result.file}`,
    `Duration  : ${result.duration_seconds ?? "unknown"} seconds`,
    `Summary   : ${result.summary}`,
    `Subtitles : ${result.subtitle_path || "not generated"}`,
    result.output_path ? `Output    : ${result.output_path}` : null,
    "Transcript preview:",
    `  "${transcriptPreview}"`,
  ]
    .filter(Boolean)
    .join("\n");
}

function formatError(status, detail) {
  const text = typeof detail === "string" ? detail : JSON.stringify(detail);

  if (status === 404) {
    return "File not found at that path. Please check the path and try again.";
  }
  if (status === 400 && text.toLowerCase().includes("unsupported")) {
    return "Unsupported file type. Supported: jpg/png/webp/bmp (images), mp4/mov/avi/mkv/webm (videos)";
  }
  if (status === 503 || /connect|refused|offline/i.test(text)) {
    return "Python service is offline. Run: docker compose up -d python-service";
  }
  return `Processing failed: ${text}`;
}

async function main() {
  const stdin = await readStdin();
  const context = parseContext(stdin);
  const filePath = path.resolve(String(context.file_path || "").trim());

  if (!filePath) {
    throw new Error("No file_path was provided to the media-processor skill.");
  }
  if (!fs.existsSync(filePath)) {
    throw new Error("File not found at that path. Please check the path and try again.");
  }

  const { route, type } = detectRoute(filePath);
  if (!route || !type) {
    throw new Error("Unsupported file type. Supported: jpg/png/webp/bmp (images), mp4/mov/avi/mkv/webm (videos)");
  }

  const response = await fetch(`${serviceBaseUrl()}${route}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath }),
  });

  let body = {};
  try {
    body = await response.json();
  } catch (_error) {
    body = {};
  }

  if (!response.ok) {
    const message = formatError(response.status, body.detail || body);
    throw new Error(message);
  }

  const output = type === "image" ? formatImageResponse(body) : formatVideoResponse(body);
  process.stdout.write(`${output}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exit(1);
});
