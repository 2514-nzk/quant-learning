// Exercise the actual source helpers and worker with a controlled fake Python runtime.
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync("reader/app.js","utf8");
const start=source.indexOf("  function prepareMath(markdown) {"),end=source.indexOf("  function typesetMath(container) {",start);
assert.ok(start>=0&&end>start);
const ctx={escapeHTML:s=>s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")};
vm.runInNewContext(source.slice(start,end),ctx);
const md=["公式 \\(x_i\\) 与 \u0060\\(literal\\)\u0060","", "~~~python","s = r'\\[not_math\\]'","~~~","", "~~~~text","~~~","\\(still_literal\\)","~~~~","","| \\(a|b\\) |","", "\\[","\\frac{1}{2}","\\]"].join("\n");
const prepared=ctx.prepareMath(md);
assert.equal((prepared.match(/data-math=/g)||[]).length,3);
assert.ok(prepared.includes("\u0060\\(literal\\)\u0060"));
assert.ok(prepared.includes("s = r'\\[not_math\\]'"));
assert.ok(prepared.includes("\\(still_literal\\)"));
assert.ok(prepared.includes("&#124;"));
assert.match(prepared,/class="math-block"/);

const workerSource=fs.readFileSync("reader/pyodide-worker.js","utf8");
let release,blocked=true,destroyed=0,stdout=()=>{}, messages=[],writes=[];
const wait=new Promise(r=>{release=r;});
const fake={
 FS:{mkdirTree(){},writeFile(p,bytes){writes.push([p,Buffer.from(bytes).toString()]);}},
 setStdout(x){stdout=x.batched;},setStderr(){},
 toPy(){return {destroy(){destroyed++;}};},
 async runPythonAsync(code,opts){if(opts){if(blocked)await wait;stdout(code);}}
};
const sandbox={self:{postMessage:m=>messages.push(m)},TextEncoder,importScripts(){},loadPyodide:async()=>fake};
vm.runInNewContext(workerSource,sandbox);
const message=(id,code)=>({data:{id,code,files:[{path:"/project/examples/x.py",content:code}],filename:"/project/examples/x.py",argv:[]}});
(async()=>{
 const first=sandbox.self.onmessage(message(1,"FIRST"));
 await sandbox.self.onmessage(message(2,"SECOND"));
 assert.equal(messages.find(m=>m.id===2).ok,false);
 release();await first;
 assert.equal(messages.find(m=>m.id===1&&m.ok).output,"FIRST\n");
 blocked=false;
 await sandbox.self.onmessage(message(3,"UPDATED"));
 assert.deepEqual(writes.map(x=>x[1]),["FIRST","UPDATED"]);
 assert.equal(messages.find(m=>m.id===3&&m.ok).output,"UPDATED\n");
 assert.equal(destroyed,2);
 console.log("PASS: math source protection, worker single-flight, updated file and cleanup (mock runtime)");
})().catch(e=>{console.error(e);process.exitCode=1;});
