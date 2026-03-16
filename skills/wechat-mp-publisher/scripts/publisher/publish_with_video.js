#!/usr/bin/env node

/*
 * Publish Markdown with mp4 references to WeChat MP draft box.
 *
 * Flow:
 * 1) detect .mp4 links in markdown
 * 2) upload video assets to WeChat material library
 * 3) replace links with placeholders
 * 4) call wenyan publish for draft creation
 * 5) patch draft HTML placeholders into iframe/mp-video tags
 */

const fs = require("fs");
const path = require("path");
const os = require("os");
const http = require("http");
const https = require("https");
const { execFileSync } = require("child_process");

const DEFAULT_THEME = "lapis";
const DEFAULT_HIGHLIGHT = "solarized-light";
const TOKEN_CACHE = path.join(os.homedir(), ".config", "wenyan-md", "token.json");

function parseArgs() {
  const args = process.argv.slice(2);
  if (args.length < 1 || args[0] === "-h" || args[0] === "--help") {
    console.log("Usage: node publish_with_video.js <markdown-file> [theme] [highlight]");
    process.exit(0);
  }
  return {
    file: path.resolve(args[0]),
    theme: args[1] || DEFAULT_THEME,
    highlight: args[2] || DEFAULT_HIGHLIGHT,
  };
}

function requireCredentials() {
  const appId = process.env.WECHAT_APP_ID || "";
  const appSecret = process.env.WECHAT_APP_SECRET || "";
  if (!appId || !appSecret) {
    throw new Error("WECHAT_APP_ID / WECHAT_APP_SECRET not set");
  }
  return { appId, appSecret };
}

function requestJson(url, options = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const mod = u.protocol === "https:" ? https : http;
    const req = mod.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method: options.method || "GET",
        headers: options.headers || {},
        timeout: options.timeout || 15000,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const body = Buffer.concat(chunks).toString("utf-8");
          try {
            resolve(JSON.parse(body));
          } catch {
            resolve({ raw: body });
          }
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("request timeout"));
    });
    if (options.body) {
      const body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
      req.write(body);
    }
    req.end();
  });
}

function uploadMultipart(url, fields) {
  return new Promise((resolve, reject) => {
    const boundary = "----FormBoundary" + Math.random().toString(36).slice(2);
    const parts = [];
    for (const field of fields) {
      if (field.filename) {
        parts.push(
          Buffer.from(
            `--${boundary}\r\n` +
              `Content-Disposition: form-data; name="${field.name}"; filename="${field.filename}"\r\n` +
              `Content-Type: ${field.contentType || "application/octet-stream"}\r\n\r\n`
          )
        );
        parts.push(fs.readFileSync(field.value));
        parts.push(Buffer.from("\r\n"));
      } else {
        parts.push(
          Buffer.from(
            `--${boundary}\r\n` +
              `Content-Disposition: form-data; name="${field.name}"\r\n\r\n${field.value}\r\n`
          )
        );
      }
    }
    parts.push(Buffer.from(`--${boundary}--\r\n`));
    const body = Buffer.concat(parts);
    const u = new URL(url);
    const mod = u.protocol === "https:" ? https : http;
    const req = mod.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method: "POST",
        headers: {
          "Content-Type": `multipart/form-data; boundary=${boundary}`,
          "Content-Length": body.length,
        },
        timeout: 180000,
      },
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf-8");
          try {
            resolve(JSON.parse(text));
          } catch {
            resolve({ raw: text });
          }
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("upload timeout"));
    });
    req.write(body);
    req.end();
  });
}

async function getToken(appId, appSecret) {
  const resp = await requestJson(
    `https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=${appId}&secret=${appSecret}`
  );
  if (!resp.access_token) {
    throw new Error(`failed to fetch token: ${JSON.stringify(resp)}`);
  }
  const token = resp.access_token;
  const cache = {
    appid: appId,
    accessToken: token,
    expireAt: Math.floor(Date.now() / 1000) + (resp.expires_in || 7200),
  };
  fs.mkdirSync(path.dirname(TOKEN_CACHE), { recursive: true });
  fs.writeFileSync(TOKEN_CACHE, JSON.stringify(cache), "utf-8");
  return token;
}

function findVideoRefs(content, baseDir) {
  const pattern = /!\[([^\]]*)\]\(([^)]+\.mp4)\)/gi;
  const refs = [];
  let m;
  while ((m = pattern.exec(content)) !== null) {
    refs.push({ alt: m[1], rel: m[2], abs: path.resolve(baseDir, m[2]) });
  }
  return refs;
}

async function uploadVideo(token, filePath, title) {
  const resp = await uploadMultipart(
    `https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=${token}&type=video`,
    [
      { name: "media", value: filePath, filename: path.basename(filePath), contentType: "video/mp4" },
      { name: "description", value: JSON.stringify({ title, introduction: title }) },
    ]
  );
  if (!resp.media_id) throw new Error(`video upload failed: ${JSON.stringify(resp)}`);
  return resp.media_id;
}

function runWenyan(file, theme, highlight) {
  const out = execFileSync("wenyan", ["publish", "-f", file, "-t", theme, "-h", highlight], {
    encoding: "utf-8",
    timeout: 120000,
  });
  const m = out.match(/Media ID[:\s]+(\S+)/);
  return { stdout: out, mediaId: m ? m[1] : "" };
}

async function patchDraft(token, draftMediaId, placeholderToMedia) {
  if (Object.keys(placeholderToMedia).length === 0 || !draftMediaId) return;
  const draft = await requestJson(`https://api.weixin.qq.com/cgi-bin/draft/get?access_token=${token}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: { media_id: draftMediaId },
  });
  if (!draft.news_item || !draft.news_item.length) return;
  const article = draft.news_item[0];
  let html = article.content || "";
  for (const [placeholder, mediaId] of Object.entries(placeholderToMedia)) {
    if (!html.includes(placeholder)) continue;
    html = html.replace(placeholder, `<mp-video data-pluginname="mpvideo" data-url="${mediaId}"></mp-video>`);
  }
  await requestJson(`https://api.weixin.qq.com/cgi-bin/draft/update?access_token=${token}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: { media_id: draftMediaId, index: 0, articles: { ...article, content: html } },
  });
}

async function main() {
  const { file, theme, highlight } = parseArgs();
  if (!fs.existsSync(file)) throw new Error(`markdown not found: ${file}`);
  const { appId, appSecret } = requireCredentials();
  const token = await getToken(appId, appSecret);
  const baseDir = path.dirname(file);
  const original = fs.readFileSync(file, "utf-8");
  const refs = findVideoRefs(original, baseDir);

  let patched = original;
  const placeholderToMedia = {};
  for (const ref of refs) {
    if (!fs.existsSync(ref.abs)) continue;
    const mediaId = await uploadVideo(token, ref.abs, ref.alt || path.basename(ref.abs, ".mp4"));
    const placeholder = `VIDEO_PLACEHOLDER_${mediaId}`;
    placeholderToMedia[placeholder] = mediaId;
    patched = patched.replace(`![${ref.alt}](${ref.rel})`, placeholder);
  }

  const temp = path.join(baseDir, `_wechat_publish_${Date.now()}.md`);
  fs.writeFileSync(temp, patched, "utf-8");
  try {
    const { stdout, mediaId } = runWenyan(temp, theme, highlight);
    const freshToken = await getToken(appId, appSecret);
    await patchDraft(freshToken, mediaId, placeholderToMedia);
    process.stdout.write(stdout);
  } finally {
    if (fs.existsSync(temp)) fs.unlinkSync(temp);
  }
}

main().catch((err) => {
  process.stderr.write(`${err.message}\n`);
  process.exit(1);
});
