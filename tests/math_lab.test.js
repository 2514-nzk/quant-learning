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

// Factor research: hand calculations, missing values and strict time boundaries.
close(m.rankingExample(0,0).ic,1);close(m.rankingExample(1,0).ic,.8);
close(m.rankingExample(6,0).ic,-1);
assert.deepEqual(m.averageRanks([4,4,2,1]),[1.5,1.5,3,4]);
assert.equal(m.rankingExample(0,2).ic,null);
assert.equal(m.rankIC([1,null],[2,3]),null);
const ic=m.icSummary(m.icExample(.05,1,0));
close(ic.avg,.05);close(ic.sd,Math.sqrt(.0039));close(ic.icir,.05/Math.sqrt(.0039));
assert.equal(m.icSummary(m.icExample(.05,0,0)).icir,null);
assert.equal(m.icSummary([.1,.1,.1]).icir,null);
assert.equal(m.icSummary([null,.1]).icir,null);assert.equal(m.icSummary([null]).avg,null);
const groups=m.quartiles(-.05,.02,0);
close(groups.groups[0].ret,-.08);close(groups.groups[3].ret,-.02);close(groups.spread,.06);
close(groups.benchmark,-.05);close(groups.excess,.03);
const missing=m.quartiles(-.05,.02,1);
assert.equal(missing.groups[3].ret,null);assert.equal(missing.spread,null);assert.equal(missing.benchmark,null);
close(missing.coverage,11/12);close(m.quartiles(-.05,.02,0,-1).spread,-.06);
for(const a of [0,2,4])for(const b of [0,1,2]){
  const r=m.neutralExample(a,b,2);
  close(r.beta,b);close(r.sizeDot,0);r.groupMeans.forEach(v=>close(v,0));
  const demean=m.neutralExample(a,b,1);demean.groupMeans.forEach(v=>close(v,0));
}
const h=m.hac([0,1,0,1],1);
close(h.ac[0],.25);close(h.ac[1],-.1875);close(h.se,.125);
close(h.iid,Math.sqrt(1/3)/2);
assert.deepEqual(m.arSample(.6),m.arSample(.6));
const ar=m.arSample(.6),bb=m.blockBootstrap(ar,8);
assert.equal(bb.means.length,600);assert.equal(bb.first.length,60);
assert.deepEqual(bb,m.blockBootstrap(ar,8));
for(let i=0;i<bb.first.length;i++)if(i%8!==0)assert.equal(bb.first[i],(bb.first[i-1]+1)%60);
assert.deepEqual(m.blockBootstrap(ar,1),m.blockBootstrap(ar,1));
const constant=m.blockBootstrap(Array(10).fill(.25),3);close(constant.low,.25);close(constant.high,.25);
const hp=m.holm([.01,.03,.08]);[.03,.06,.08].forEach((v,i)=>close(hp[i],v));
const shuffled=m.holm([.08,.01,.03]);[.08,.03,.06].forEach((v,i)=>close(shuffled[i],v));
assert.deepEqual(m.holm([.9,.9,1]),[1,1,1]);
const row=m.timeline(5,0);
assert.equal(m.purgeRows(row,10,0).find(r=>r.signal===5).allowed,false);
assert.equal(m.purgeRows(m.timeline(4,0),10,0).find(r=>r.signal===5).allowed,false);
assert.equal(m.purgeRows(m.timeline(3,0),10,0).find(r=>r.signal===5).allowed,true);
assert.equal(m.purgeRows(m.timeline(3,0),10,1).find(r=>r.signal===5).allowed,false);
const rr=m.rollingAt(row,75,0,8);
assert.ok(rr.leaked>0);assert.ok(rr.allowed.every(r=>r.available<75));
const changed=row.map(r=>r.available>=75?{...r,y:r.y+100*r.x+3}:r);
const rr2=m.rollingAt(changed,75,0,8);
close(rr.strictPrediction,rr2.strictPrediction);
assert.notEqual(rr.naivePrediction,rr2.naivePrediction);
const researchRoutes={"advanced/volume-2/01_research_protocol.md":["rankic"],
"advanced/volume-2/03_time_series.md":["hac","bootstrap"],"advanced/volume-2/06_labels_splits.md":["purge"],
"advanced/volume-2/07_factor_engineering.md":["neutral"],"advanced/volume-2/08_factor_validation.md":["icir","quartiles","hac","bootstrap","holm"],
"advanced/volume-2/11_oos_drift.md":["rolling"],"教程/真实_08_单因子评价.md":["rankic"]};
for(const [file,ids] of Object.entries(researchRoutes)){
 const md=fs.readFileSync(file,"utf8");
 assert.deepEqual([...md.matchAll(/data-lesson-lab="([^"]+)"/g)].map(a=>a[1]),ids);
}
assert.equal(Object.keys(m.labs).length,17);
console.log("PASS: nine factor research and inference labs, strict timing and missing data");
