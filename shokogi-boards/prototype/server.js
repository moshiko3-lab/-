// Shokogi boards: serves index.html and keeps all data in data.json next to this file.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const PORT = 5050;
const URL_ = 'http://127.0.0.1:' + PORT;
const DATA = path.join(__dirname, 'data.json');
const PAGE = path.join(__dirname, 'index.html');
const PHOTOS = path.join(__dirname, 'photos');
fs.mkdirSync(PHOTOS, { recursive: true });

// A corrupt data.json crashes here on purpose instead of being silently overwritten.
let data = fs.existsSync(DATA) ? JSON.parse(fs.readFileSync(DATA, 'utf8')) : { boards: [], renters: [] };
data.rev ??= 1;

function save(d) {
  fs.writeFileSync(DATA + '.tmp', JSON.stringify(d, null, 2));
  fs.renameSync(DATA + '.tmp', DATA); // atomic: a crash mid-write never leaves a half file
}

function readBody(req, cb) {
  const chunks = [];
  req.on('data', c => chunks.push(c));
  req.on('end', () => cb(Buffer.concat(chunks)));
}

function send(res, code, obj) {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(obj));
}

// The client saves the whole state. `rev` makes a save from an outdated copy (a second window,
// or an old tab) fail with 409 instead of silently overwriting newer data.
// ponytail: when Bloowatch starts adding renters from here, bump rev the same way.
const server = http.createServer((req, res) => {
  if (req.url === '/api/data' && req.method === 'GET') return send(res, 200, data);
  if (req.url === '/api/data' && req.method === 'PUT') {
    readBody(req, body => {
      try {
        const d = JSON.parse(body.toString());
        if (!Array.isArray(d.boards) || !Array.isArray(d.renters)) throw new Error('bad data');
        if (d.rev !== data.rev) return send(res, 409, { error: 'outdated copy' });
        d.rev = data.rev + 1;
        save(d);
        data = d;
        send(res, 200, { rev: d.rev });
      } catch (e) {
        send(res, 400, { error: e.message });
      }
    });
    return;
  }
  // Board photos: photos/<board id>.jpg. The strict name pattern blocks paths like ../
  const photo = req.url.match(/^\/photos\/([\w-]+\.jpg)(\?.*)?$/);
  if (photo) {
    const file = path.join(PHOTOS, photo[1]);
    if (req.method === 'PUT') return readBody(req, buf => fs.writeFile(file, buf, err => send(res, err ? 500 : 200, {})));
    if (req.method === 'DELETE') return fs.unlink(file, () => send(res, 200, {}));
    return fs.readFile(file, (err, buf) => {
      res.writeHead(err ? 404 : 200, { 'Content-Type': 'image/jpeg' });
      res.end(buf);
    });
  }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  fs.createReadStream(PAGE).pipe(res);
});

const openBrowser = () => process.argv.includes('--open') &&
  exec((process.platform === 'win32' ? 'start "" ' : 'open ') + URL_);

server.on('error', e => {
  if (e.code !== 'EADDRINUSE') throw e;
  console.log('Already running at ' + URL_);
  openBrowser();
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('Shokogi boards running at ' + URL_ + ' - keep this window open.');
  openBrowser();
});
