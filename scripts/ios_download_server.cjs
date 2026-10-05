#!/usr/bin/env node
// Serve only the published NAS release, never the NAS root or signing material.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = '/mnt/nas/A2AMonitor/20261005/download';
const prefix = '/downloads/a2amonitor/20261005';
const allowed = new Map([
  ['index.html', 'text/html; charset=utf-8'], ['manifest.plist', 'application/xml'],
  ['proof.json', 'application/json'], ['A2AMonitor-1.0.0-2.ipa', 'application/octet-stream'],
  ['A2AMonitor-1.0.0-3.ipa', 'application/octet-stream'],
]);
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); return res.end(); }
  if (url.pathname === prefix) { res.writeHead(302, { Location: prefix + '/' }); return res.end(); }
  const name = url.pathname.startsWith(prefix + '/') ? url.pathname.slice(prefix.length + 1) || 'index.html' : '';
  if (!allowed.has(name)) { res.writeHead(404); return res.end(); }
  const file = path.join(root, name);
  let stat;
  try { stat = fs.statSync(file); } catch { res.writeHead(404); return res.end(); }
  let start = 0, end = stat.size - 1, status = 200;
  const headers = { 'Content-Type': allowed.get(name), 'Accept-Ranges': 'bytes',
    'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache' };
  if (req.headers.range) {
    const match = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range);
    if (!match) { res.writeHead(416); return res.end(); }
    start = Number(match[1]); end = match[2] ? Number(match[2]) : end;
    if (start > end || end >= stat.size) { res.writeHead(416); return res.end(); }
    status = 206; headers['Content-Range'] = `bytes ${start}-${end}/${stat.size}`;
  }
  headers['Content-Length'] = end - start + 1;
  res.writeHead(status, headers);
  if (req.method === 'HEAD') return res.end();
  fs.createReadStream(file, { start, end }).on('error', () => res.destroy()).pipe(res);
}).listen(18772, '127.0.0.1', () => console.log('NAS release gateway listening on loopback 18772'));






