const http = require('http');
const fs = require('fs');
const path = require('path');
const host = '192.168.50.101';
const port = 8769;
const siteRoot = path.join(__dirname, 'site');
const indexPath = path.join(siteRoot, 'index.html');

const server = http.createServer((req, res) => {
  if (req.method !== 'GET') {
    res.writeHead(405, {'Content-Type': 'text/plain'});
    res.end('Method Not Allowed');
    return;
  }
  if (req.url === '/' || req.url === '/index.html') {
    fs.readFile(indexPath, (err, data) => {
      if (err) {
        res.writeHead(500, {'Content-Type': 'text/plain'});
        res.end('Internal Server Error');
        return;
      }
      res.writeHead(200, {'Content-Type': 'text/html'});
      res.end(data);
    });
    return;
  }
  res.writeHead(404, {'Content-Type': 'text/plain'});
  res.end('Not Found');
});

server.listen(port, host, () => {
  console.log(`Listening on ${host}:${port}`);
});
