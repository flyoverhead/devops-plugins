import { exec, execFile } from "child_process";
import * as fs from "fs";
import express from "express";

const app = express();

app.post("/unpack", (req, res) => {
  const name = req.query.name as string;
  // ruleid: variant-taint-ts
  exec(`gzip -d /srv/in/${name}`, () => res.end());
});

app.post("/count", (req, res) => {
  // ok: variant-taint-ts
  execFile("wc", ["-l", String(req.body.file)], () => res.end());
});

app.get("/report", async (req, res) => {
  // ruleid: variant-taint-ts
  const rows = await db.query("SELECT * FROM jobs WHERE owner = '" + req.params.owner + "'");
  // ok: variant-taint-ts
  const safe = await db.query("SELECT * FROM jobs WHERE owner = $1", [req.params.owner]);
  res.json({ rows, safe });
});

app.get("/conf", (req, res) => {
  // ruleid: variant-taint-ts
  res.send(fs.readFileSync(process.env.DEMO_CONFIG as string));
});

app.get("/page", (req, res) => {
  const n = parseInt(req.query.n as string, 10);
  // ok: variant-taint-ts
  exec("seq " + n, () => res.end());
});

declare const db: { query(q: string, args?: unknown[]): Promise<unknown> };
