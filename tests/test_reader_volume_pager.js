// Regression test: the three books must never masquerade as one chapter chain.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const source = fs.readFileSync("reader/app.js", "utf8");
const start = source.indexOf("  function volumeOf(doc) {");
const end = source.indexOf("  function updateReadingProgress() {", start);
assert.ok(start >= 0 && end > start, "volume-aware pager helper is present");
const functions = source.slice(start, end);
function widget() {
  const label = { textContent: "" };
  const title = { textContent: "" };
  return { disabled: false, dataset: { path: "" },
    querySelector(selector) { return selector === "span" ? label : title; },
    label, title };
}
function check(docs, activeIndex) {
  const previous = widget(), next = widget();
  const sandbox = { documents: docs, current: docs[activeIndex], els: { previous, next } };
  vm.runInNewContext(functions + "\nupdatePager(" + activeIndex + ");", sandbox);
  return { previous, next };
}
const docs = [
  { path: "教程/真实_16_综合练习.md", group: "第四循环", title: "第一卷末章" },
  { path: "教程/真实_附录.md", group: "工具与参考", title: "第一卷附录" },
  { path: "advanced/volume-2/README.md", group: "第二卷", title: "第二卷目录" },
  { path: "advanced/volume-2/01_research_protocol.md", group: "第二卷", title: "第二卷第1章" },
  { path: "advanced/volume-2/14_reproducible_capstone.md", group: "第二卷", title: "第二卷末章" },
  { path: "advanced/volume-3/README.md", group: "第三卷", title: "第三卷目录" },
  { path: "advanced/volume-3/01_strategy_contract.md", group: "第三卷", title: "第三卷第1章" },
];
let result = check(docs, 1);
assert.equal(result.next.dataset.path, "__home__");
assert.match(result.next.label.textContent, /本卷读完/);
assert.match(result.next.title.textContent, /返回书架/);
result = check(docs, 2);
assert.equal(result.previous.dataset.path, "__home__");
assert.equal(result.next.dataset.path, "advanced/volume-2/01_research_protocol.md");
result = check(docs, 3);
assert.equal(result.previous.dataset.path, "advanced/volume-2/README.md");
assert.equal(result.next.dataset.path, "advanced/volume-2/14_reproducible_capstone.md");
result = check(docs, 4);
assert.equal(result.next.dataset.path, "__home__");
result = check(docs, 5);
assert.equal(result.previous.dataset.path, "__home__");
assert.equal(result.next.dataset.path, "advanced/volume-3/01_strategy_contract.md");
result = check(docs, 6);
assert.equal(result.next.disabled, true);
assert.equal(result.next.dataset.path, "");
console.log("Three-volume pager boundary tests passed.");
