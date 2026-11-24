const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const m=require("../reader/math-lab.js");
const close=(a,b,eps=1e-10)=>assert.ok(Math.abs(a-b)<eps,a+" != "+b);
const b=m.bayes(.1,.7,.2);
close(b.tp,70);close(b.fp,180);close(b.posterior,.28);close(b.tp+b.fp+b.fn+b.tn,1000);
assert.equal(m.bayes(.5,0,0).posterior,null);
for(const rho of [-1,-.5,0,.5,1]){
  const a=m.correlation(rho,1),b=m.correlation(rho,2);
  close(a.rho,rho);close(b.rho,rho);close(b.cov,2*a.cov);
}
assert.equal(m.correlation(.5,0).rho,null);
close(m.moments([1,2,3],[2,4,6]).cov,2);
close(m.ridge(0).slope,2);close(m.ridge(1).slope,.8);close(m.ridge(1,6).intercept,2);
assert.ok(m.ridge(5).slope<m.ridge(1).slope);
const g=m.gradient(1,.1,100);
close(g.rows.at(-1).beta,g.solution);close(g.rows.at(-1).loss,g.optimalLoss);
assert.equal(m.gradient(1,.7,20).stable,false);
assert.ok(m.gradient(1,.7,20).rows.at(-1).loss>m.gradient(1,.7,20).rows[0].loss);
const ci=m.confidence(.05,.2,100);
close(ci.low,.0108);close(ci.high,.0892);
assert.ok(m.confidence(.05,.2,200).se<ci.se);
let prev=Infinity;
for(let depth=0;depth<=5;depth++){
  const r=m.treeExperiment(depth);
  assert.ok(r.leaves<=2**depth);
  assert.ok(r.trainError<=prev+1e-12);
  prev=r.trainError;
}
const t=m.fitTree([{x:0,y:1},{x:1,y:1},{x:2,y:4},{x:3,y:4}],1);
close(t.threshold,1.5);close(m.predict(t,0),1);close(m.predict(t,3),4);
const boost=m.boosting(.2,40);
assert.equal(boost.history.length,41);
for(let i=1;i<boost.history.length;i++)assert.ok(boost.history[i].train<=boost.history[i-1].train+1e-12);
close(m.boosting(.2,0).prediction(3),boost.base);
for(const rho of [-1,0,1])for(const gamma of [0,2,10])for(const cap of [0,.4,1]){
  const r=m.portfolio(rho,gamma,cap);
  for(const p of r.points){
    assert.ok(p.a>=0&&p.b>=0&&p.cash>=-1e-12&&p.a<=cap+1e-12&&p.b<=cap+1e-12);
    close(p.a+p.b+p.cash,1);
    assert.ok(r.best.objective>=p.objective-1e-10);
  }
  for(const p of r.frontier)assert.ok(!r.points.some(q=>q.risk<=p.risk+1e-12&&q.ret>p.ret+1e-10));
}
close(m.portfolio(-1,2,1).points.find(p=>p.a===.6&&p.b===.4).risk,0,1e-8);
close(m.portfolio(0,0,1).best.b,1);
// Every experiment produces finite markup at default and slider extremes.
for(const [key,lab] of Object.entries(m.labs)){
  for(const mode of ["min","max","value"]){
    const values=Object.fromEntries(lab.controls.map(c=>[c.key,c[mode]]));
    const html=lab.render(values);
    assert.ok(html.includes("mathlab-metrics"),key);
    assert.doesNotMatch(html,/NaN|Infinity|undefined/);
  }
}
const routes={"advanced/volume-2/02_math_statistics.md":["bayes","correlation","ridge","gradient","confidence"],
 "advanced/volume-2/10_machine_learning.md":["ridge","tree","boost"],"advanced/volume-2/12_portfolio_optimization.md":["portfolio"],
 "教程/真实_11_线性模型.md":["ridge"],"教程/真实_12_树与森林.md":["tree"],"教程/真实_13_逐步提升模型.md":["boost"]};
for(const [file,ids] of Object.entries(routes)){
  const md=fs.readFileSync(file,"utf8");
  assert.deepEqual([...md.matchAll(/data-lesson-lab="([^"]+)"/g)].map(a=>a[1]),ids);
}
const html=fs.readFileSync("reader/index.html","utf8"),builder=fs.readFileSync("reader/build_reader.py","utf8"),app=fs.readFileSync("reader/app.js","utf8");
assert.ok(html.indexOf("math-lab.js")<html.indexOf("app.js?v="));
assert.match(builder,/copy2\(ROOT \/ "reader" \/ "math-lab.js", output \/ "math-lab.js"\)/);
assert.match(app,/QuantMathLab\?\.mount\(els.article\)/);
console.log("PASS: eight math lab calculations, boundary cases, rendering and chapter placement");
