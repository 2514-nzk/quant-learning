// No npm packages required: run with node tests/real_browser_lab.test.js
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const { run, rankIc, summarize } = require("../reader/real-case.js");
const sample = JSON.parse(fs.readFileSync(path.join(root, "data/real_a_share/teaching_case.json"), "utf-8"));

assert.equal(sample.rounds.length, 18);
assert.equal(rankIc(sample.intro.rows), -1);
const whole = summarize(sample.rounds);
assert.equal(whole.periods, 18);
assert.ok(Math.abs(whole.meanIc - (-0.1222222222222222)) < 0.000001);
assert.ok(Math.abs(whole.strategyPct - 14.85867224) < 0.0001);

const output = run(sample);
for (const phrase of [
  "寒武纪", "宁德时代", "比亚迪", "贵州茅台",
  "2024-06-21", "2024-06-24", "2024-06-28",
  "954,338.69", "985,218.01", "954,882.00",
  "18 个历史观察期", "RankIC", "没有执行 Python 程序",
]) {
  assert.ok(output.includes(phrase), "Lab output missing " + phrase);
}
const broken = JSON.parse(JSON.stringify(sample));
delete broken.rounds;
assert.throws(() => run(broken), /课堂历史数据不完整/);
const incomplete = JSON.parse(JSON.stringify(sample));
delete incomplete.rounds[0].rows[0].mom5;
assert.throws(() => run(incomplete), /部分股票历史数据不完整/);

const reader = fs.readFileSync(path.join(root, "reader/app.js"), "utf-8");
const html = fs.readFileSync(path.join(root, "reader/index.html"), "utf-8");
const builder = fs.readFileSync(path.join(root, "reader/build_reader.py"), "utf-8");
assert.match(html, /src="\.\/real-case\.js\?v=1"/);
assert.match(html, /src="\.\/app\.js\?v=\d+"/);
assert.ok(html.indexOf("real-case.js?v=1") < html.indexOf("app.js?v="));
assert.match(reader, /lab\.kind === "real-data"/);
assert.match(reader, /QuantRealCase\.run\(sample\)/);
assert.equal((builder.match(/"kind": "real-data"/g) || []).length, 3);
assert.match(builder, /"real-case\.js"/);
console.log("PASS: real-history browser calculation, 18 rounds, missing-data safeguards, script wiring");
