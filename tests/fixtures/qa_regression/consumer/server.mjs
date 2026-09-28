// Local fixture app for CPP issue #1291. Serves ONE page whose "Add to cart"
// button is either buggy (the count moves by two per click) or fixed (by one),
// selected by FIXTURE_STATE. Synthetic data only; nothing here is private.
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';

const state = process.env.FIXTURE_STATE === 'fixed' ? 'fixed' : 'buggy';
const port = Number(process.env.FIXTURE_PORT || 4391);
const page = readFileSync(new URL(`./public/${state}.html`, import.meta.url));

createServer((req, res) => {
  if (req.url === '/healthz') {
    res.writeHead(200, { 'content-type': 'text/plain' });
    res.end(`ok ${state}\n`);
    return;
  }
  if (req.url === '/' || req.url === '/shop') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end(page);
    return;
  }
  res.writeHead(404, { 'content-type': 'text/plain' });
  res.end('not found\n');
}).listen(port, '127.0.0.1');
