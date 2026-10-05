const http = require('http');
const fs = require('fs');
const path = require('path');
const host = '192.168.50.101';
const port = 8768;
const indexPath = path.join(__dirname, 'site', 'index.html');
let indexHtml = null;
try {
  indexHtml = fs.readFileSync(indexPath, 'utf8');
} catch (e) {
  console.error('Failed to read index.html:', e);
  process.exit(1);
}
const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url === '/index.html') {
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
    res.end(indexHtml);
  } else {
    res.writeHead(404, {'Content-Type': 'text/plain; charset=utf-8'});
    res.end('404 Not Found');
  }
});
server.listen(port, host, () => {
  console.log(`Listening on http://${host}:${port}/`);
});
