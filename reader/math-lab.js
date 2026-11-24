/* Interactive mathematics: deterministic, synthetic classroom examples only.
 * Pure numerical functions are shared by the page and Node regression tests.
 */
(function(root){
  "use strict";
  const mean=x=>x.reduce((a,b)=>a+b,0)/x.length;
  const mse=(a,b)=>mean(a.map((v,i)=>(v-b[i])**2));
  const fmt=(v,d=3)=>Number.isFinite(v)?v.toFixed(d):"未定义";
  const pct=v=>Number.isFinite(v)?(v*100).toFixed(2)+"%":"未定义";
  function bayes(base,hit,falseAlarm){
    if([base,hit,falseAlarm].some(v=>!Number.isFinite(v)||v<0||v>1))throw Error("概率必须在 0–1");
    const tp=1000*base*hit,fp=1000*(1-base)*falseAlarm;
    return {tp,fp,fn:1000*base-tp,tn:1000*(1-base)-fp,posterior:tp+fp?tp/(tp+fp):null};
  }
  function moments(x,y){
    const mx=mean(x),my=mean(y);
    const xx=x.reduce((s,v)=>s+(v-mx)**2,0),yy=y.reduce((s,v)=>s+(v-my)**2,0);
    const xy=x.reduce((s,v,i)=>s+(v-mx)*(y[i]-my),0);
    return {mx,my,varx:xx/(x.length-1),vary:yy/(x.length-1),cov:xy/(x.length-1),
      rho:xx&&yy?xy/Math.sqrt(xx*yy):null};
  }
  function correlation(rho,scale){
    const x=[-3,-2,-1,0,1,2,3],z=[1,-1,-1,2,-1,-1,1];
    const m=moments(x,z),k=Math.sqrt(m.varx/m.vary);
    const y=x.map((v,i)=>scale*(rho*v+Math.sqrt(Math.max(0,1-rho*rho))*k*z[i]));
    return {x,y,...moments(x,y)};
  }
  function ridge(lambda,outlier=0){
    const x=[-1,0,1],y=[-2,0,2+outlier],m=moments(x,y);
    const vx=mean(x.map(v=>(v-m.mx)**2)),cov=mean(x.map((v,i)=>(v-m.mx)*(y[i]-m.my)));
    const slope=cov/(vx+lambda),intercept=m.my-slope*m.mx;
    const error=mse(y,x.map(v=>intercept+slope*v)),penalty=lambda*slope*slope;
    return {x,y,slope,intercept,error,penalty,objective:error+penalty,vx,cov};
  }
  function gradient(lambda,eta,steps){
    const r=ridge(lambda),a=r.vx+lambda,b=r.cov;
    const objective=v=>mean(r.x.map((x,i)=>(r.y[i]-v*x)**2))+lambda*v*v;
    let beta=0,rows=[{step:0,beta,loss:objective(beta)}];
    for(let i=1;i<=steps;i++){
      beta-=eta*2*(a*beta-b);
      rows.push({step:i,beta,loss:objective(beta)});
    }
    return {rows,solution:r.slope,optimalLoss:r.objective,limit:1/a,stable:eta>0&&eta<1/a};
  }
  function confidence(avg,sd,n){
    const se=sd/Math.sqrt(n),margin=1.96*se;
    return {se,low:avg-margin,high:avg+margin};
  }
  // Fixed interleaved design: a train-only model; disclosed test data are for learning.
  const train=Array.from({length:16},(_,i)=>({x:i,y:Math.sin(i*.55)+[.38,-.42,.31,-.25][i%4]}));
  const test=Array.from({length:15},(_,i)=>({x:i+.5,y:Math.sin((i+.5)*.55)+[.08,-.12,.04][i%3]}));
  function fitTree(rows,depth){
    const value=mean(rows.map(r=>r.y)),leaf={value};
    if(depth<=0||rows.length<2)return leaf;
    const sorted=[...rows].sort((a,b)=>a.x-b.x);
    let best=null,bestLoss=rows.reduce((s,r)=>s+(r.y-value)**2,0);
    for(let i=1;i<sorted.length;i++){
      if(sorted[i-1].x===sorted[i].x)continue;
      const left=sorted.slice(0,i),right=sorted.slice(i);
      const loss=[left,right].reduce((s,g)=>{const m=mean(g.map(r=>r.y));return s+g.reduce((q,r)=>q+(r.y-m)**2,0);},0);
      if(loss<bestLoss-1e-12){bestLoss=loss;best={threshold:(sorted[i-1].x+sorted[i].x)/2,left,right};}
    }
    if(!best)return leaf;
    return {value,threshold:best.threshold,left:fitTree(best.left,depth-1),right:fitTree(best.right,depth-1)};
  }
  function predict(tree,x){return tree.threshold===undefined?tree.value:predict(x<tree.threshold?tree.left:tree.right,x);}
  function leaves(tree){return tree.threshold===undefined?1:leaves(tree.left)+leaves(tree.right);}
  function treeExperiment(depth){
    const tree=fitTree(train,depth),prediction=x=>predict(tree,x);
    return {train,test,tree,leaves:leaves(tree),prediction,trainError:mse(train.map(r=>r.y),train.map(r=>prediction(r.x))),
      testError:mse(test.map(r=>r.y),test.map(r=>prediction(r.x)))};
  }
  function boosting(rate,rounds){
    const base=mean(train.map(r=>r.y)),trees=[];
    const prediction=x=>base+rate*trees.reduce((s,t)=>s+predict(t,x),0);
    const errors=()=>({train:mse(train.map(r=>r.y),train.map(r=>prediction(r.x))),test:mse(test.map(r=>r.y),test.map(r=>prediction(r.x)))});
    const history=[{round:0,...errors()}];
    for(let i=1;i<=rounds;i++){
      trees.push(fitTree(train.map(r=>({x:r.x,y:r.y-prediction(r.x)})),1));
      history.push({round:i,...errors()});
    }
    return {train,test,prediction,history,base,...history[history.length-1]};
  }
  function portfolio(rho,gamma,cap){
    // Both expected returns and volatilities use the same artificial annual horizon.
    const mu=[.08,.12],sig=[.20,.30],points=[];
    for(let i=0;i<=100;i+=2)for(let j=0;j<=100-i;j+=2){
      const a=i/100,b=j/100;
      if(a>cap+1e-10||b>cap+1e-10)continue;
      const ret=a*mu[0]+b*mu[1],variance=Math.max(0,(a*sig[0])**2+(b*sig[1])**2+2*a*b*sig[0]*sig[1]*rho);
      points.push({a,b,cash:1-a-b,ret,risk:Math.sqrt(variance),objective:ret-gamma*variance});
    }
    const best=points.reduce((a,b)=>b.objective>a.objective+1e-12?b:a);
    const sorted=[...points].sort((a,b)=>a.risk-b.risk||b.ret-a.ret);
    let max=-Infinity;
    const frontier=sorted.filter(p=>{if(p.ret>max+1e-12){max=p.ret;return true;}return false;});
    return {points,best,frontier};
  }

  // DOM layer: native controls, self-contained SVG, no CDN or Python required.
  const colors={ink:"#64748b",a:"#258b82",b:"#bc7548",warn:"#b95757"};
  const control=(key,label,min,max,step,value)=>({key,label,min,max,step,value});
  const metrics=items=>'<div class="mathlab-metrics">'+items.map(([n,v])=>'<div><small>'+n+'</small><strong>'+v+'</strong></div>').join("")+'</div>';
  function plot({series=[],dots=[],xd,yd,xlabel,ylabel}){
    const width=640,height=260,l=62,r=620,t=15,b=213;
    const all=[...series.flatMap(s=>s.points),...dots.flatMap(s=>s.points)].filter(p=>p.every(Number.isFinite));
    if(!all.length)return '<p>暂无有限数值。</p>';
    const bounds=(arr,provided)=>{if(provided)return provided;const lo=Math.min(...arr),hi=Math.max(...arr),pad=(hi-lo||1)*.08;return [lo-pad,hi+pad];};
    const [x0,x1]=bounds(all.map(p=>p[0]),xd),[y0,y1]=bounds(all.map(p=>p[1]),yd);
    const X=x=>l+(x-x0)/(x1-x0)*(r-l),Y=y=>b-(y-y0)/(y1-y0)*(b-t);
    let svg='<svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="'+xlabel+' 与 '+ylabel+' 的教学图">';
    for(let i=0;i<=4;i++){
      const xx=x0+(x1-x0)*i/4,yy=y0+(y1-y0)*i/4;
      svg+='<path d="M'+l+' '+Y(yy)+' H'+r+'" stroke="currentColor" opacity=".12"/><text x="'+(l-7)+'" y="'+(Y(yy)+4)+'" text-anchor="end">'+fmt(yy,2)+'</text><text x="'+X(xx)+'" y="'+(b+17)+'" text-anchor="middle">'+fmt(xx,2)+'</text>';
    }
    svg+='<path d="M'+l+' '+t+' V'+b+' H'+r+'" fill="none" stroke="currentColor" opacity=".4"/>';
    for(const s of series){const p=s.points.filter(p=>p.every(Number.isFinite));svg+='<polyline points="'+p.map(([x,y])=>X(x)+','+Y(y)).join(" ")+'" fill="none" stroke="'+s.color+'" stroke-width="2.5" stroke-linejoin="round"/>';}
    for(const s of dots)for(const [x,y] of s.points.filter(p=>p.every(Number.isFinite)))svg+='<circle cx="'+X(x)+'" cy="'+Y(y)+'" r="'+(s.radius||4)+'" fill="'+s.color+'" opacity="'+(s.opacity||1)+'"/>';
    svg+='<text x="'+((l+r)/2)+'" y="253" text-anchor="middle">'+xlabel+'</text><text x="'+l+'" y="11">'+ylabel+'</text></svg>';
    const legend=[...series,...dots].filter(s=>s.name).map(s=>'<span><i style="background:'+s.color+'"></i>'+s.name+'</span>').join("");
    return svg+'<div class="risk-legend">'+legend+'</div>';
  }
  const xy=(x,y)=>x.map((v,i)=>[v,y[i]]);
  const fitPlot=r=>plot({series:[{name:"模型预测",color:colors.a,points:Array.from({length:301},(_,i)=>[i/20,r.prediction(i/20)])}],
    dots:[{name:"训练点",color:colors.ink,points:r.train.map(v=>[v.x,v.y])},{name:"公开验证点",color:colors.b,points:r.test.map(v=>[v.x,v.y])}],xd:[0,15],yd:[-1.6,1.6],xlabel:"人工特征 x",ylabel:"人工目标 y"});
  const labs={
    bayes:{title:"信号命中率高，为什么仍然可能不赚钱？",intro:"先用第 02 章的 10% / 70% / 20% 例子，再分别改变三项概率。",
      controls:[control("base","基础上涨率（%）",0,100,1,10),control("hit","上涨时信号命中率（%）",0,100,1,70),control("falseAlarm","未上涨时误报率（%）",0,100,1,20)],
      render:v=>{const a=bayes(v.base/100,v.hit/100,v.falseAlarm/100);return metrics([["出现信号后的上涨率",pct(a.posterior)],["信号总数（期望）",fmt(a.tp+a.fp,1)]])+
        '<table><thead><tr><th>每 1000 条观察的期望数</th><th>有信号</th><th>无信号</th></tr></thead><tbody><tr><td>上涨</td><td>'+fmt(a.tp,1)+'</td><td>'+fmt(a.fn,1)+'</td></tr><tr><td>未上涨</td><td>'+fmt(a.fp,1)+'</td><td>'+fmt(a.tn,1)+'</td></tr></tbody></table><p>分母是有信号的两类之和；没有信号时条件概率未定义。这里只算概率，未考虑收益幅度和成本。</p>';}},
    correlation:{title:"相关系数与协方差到底差在哪？",intro:"移动相关系数，让散点从同向变为反向；再改变 Y 的数值尺度。",
      controls:[control("rho","构造相关系数",-1,1,.1,.5),control("scale","Y 尺度",0,3,.25,1)],
      render:v=>{const r=correlation(v.rho,v.scale);return metrics([["样本协方差",fmt(r.cov)],["实际相关系数",fmt(r.rho)]])+plot({dots:[{name:"七个人工配对观察",color:colors.a,points:xy(r.x,r.y)}],xd:[-3.5,3.5],xlabel:"X",ylabel:"Y"})+'<p>放大 Y 会改变协方差，却不改变非零尺度下的相关系数。Y 恒定时相关未定义。散点是按设定相关性构造，不是市场观测。</p>';}},
    ridge:{title:"Ridge：为什么惩罚越大，直线越平？",intro:"使用课本的三个点，截距不惩罚。还可以把最后一个 y 改成异常值。",
      controls:[control("lambda","惩罚 λ",0,5,.1,1),control("outlier","末点额外偏差",0,6,.5,0)],
      render:v=>{const r=ridge(v.lambda,v.outlier),ols=ridge(0,v.outlier);return metrics([["Ridge 斜率",fmt(r.slope)],["截距",fmt(r.intercept)],["训练 MSE",fmt(r.error)],["惩罚后目标 J",fmt(r.objective)]])+plot({series:[{name:"OLS",color:colors.ink,points:[[-1,ols.intercept-ols.slope],[1,ols.intercept+ols.slope]]},{name:"Ridge",color:colors.a,points:[[-1,r.intercept-r.slope],[1,r.intercept+r.slope]]}],dots:[{name:"训练点",color:colors.b,points:xy(r.x,r.y)}],xd:[-1.15,1.15],xlabel:"特征 x",ylabel:"目标 y"})+'<p>目标 J = MSE + λ × 斜率²。当前惩罚为 '+fmt(r.penalty)+'。λ=1、无异常值时斜率为 0.8；训练误差变大不自动证明泛化更好。</p>';}},
    gradient:{title:"梯度下降：步子太大为什么会越走越远？",intro:"从 β=0 出发，使用同一中心化三点 Ridge 目标，画出逐次迭代。",
      controls:[control("lambda","惩罚 λ",0,2,.1,1),control("eta","学习率 η",.01,.8,.01,.1),control("steps","迭代次数",1,20,1,10)],
      render:v=>{const r=gradient(v.lambda,v.eta,v.steps),last=r.rows.at(-1);return metrics([["当前系数",fmt(last.beta)],["闭式最优系数",fmt(r.solution)],["当前目标",fmt(last.loss)],["收敛学习率上界",fmt(r.limit)]])+plot({series:[{name:"J(β) 每步",color:colors.a,points:r.rows.map(a=>[a.step,a.loss])},{name:"理论最小值",color:colors.ink,points:[[0,r.optimalLoss],[v.steps,r.optimalLoss]]}],xlabel:"迭代次数",ylabel:"目标函数 J"})+'<p>'+(r.stable?"当前步长在此二次目标的收敛范围内。":"当前步长达到或超过此二次目标的收敛上界，可能振荡或发散。")+' 该上界只适用于本实验的固定二次目标。</p>';}},
    confidence:{title:"同样平均 IC，为什么可信程度不同？",intro:"假定独立观测并采用正态近似，比较样本数与波动对区间宽度的影响。",
      controls:[control("avg","平均 IC",-.15,.15,.01,.05),control("sd","IC 样本标准差",.02,.4,.02,.2),control("n","独立观察期数",10,200,10,100)],
      render:v=>{const r=confidence(v.avg,v.sd,v.n);return metrics([["均值标准误",fmt(r.se,4)],["近似 95% 区间","["+fmt(r.low,4)+", "+fmt(r.high,4)+"]"]])+plot({series:[{name:"95% 区间",color:colors.a,points:[[r.low,0],[r.high,0]]},{name:"零假设参考",color:colors.ink,points:[[0,-.35],[0,.35]]}],dots:[{name:"样本平均",color:colors.b,points:[[v.avg,0]]}],xd:[-.45,.45],yd:[-.5,.5],xlabel:"平均 IC",ylabel:"区间示意"})+'<p>当前区间'+(r.low<=0&&r.high>=0?"包含":"不包含")+'零。真实周度 IC 可能有自相关；小样本或非正态场景不能机械套用此近似。</p>';}},
    tree:{title:"决策树：越深越好吗？",intro:"对固定人工数据训练真实的一维平方误差回归树。只用实心训练点找切分，不用验证点选切分。",
      controls:[control("depth","最大树深度",0,5,1,2)],
      render:v=>{const r=treeExperiment(v.depth);return metrics([["叶节点数",r.leaves],["训练 MSE",fmt(r.trainError,4)],["公开验证 MSE",fmt(r.testError,4)]])+fitPlot(r)+'<p>深度 0 只有一个均值；更深的树可以分出更多区间。验证误差不一定随训练误差下降。此处不是随机森林。</p>';}},
    boost:{title:"Boosting：下一棵树怎样修正上一轮？",intro:"从训练均值出发，每轮用一棵深度 1 的回归树拟合当前训练残差，再乘学习率加到预测。",
      controls:[control("rate","学习率",.05,1,.05,.2),control("rounds","树的数量",0,40,1,12)],
      render:v=>{const r=boosting(v.rate,v.rounds);return metrics([["训练 MSE",fmt(r.train,4)],["公开验证 MSE",fmt(r.test,4)],["初始预测均值",fmt(r.base)]])+fitPlot({...r,train, test})+plot({series:[{name:"训练误差",color:colors.a,points:r.history.map(q=>[q.round,q.train])},{name:"验证误差",color:colors.b,points:r.history.map(q=>[q.round,q.test])}],xlabel:"树的数量",ylabel:"MSE"})+'<p>这是用平方损失、逐轮拟合残差的最小 Boosting 实现，不是 LightGBM 软件库，也未实现其直方图、叶子优先生长等机制。验证集已经公开，不能当独立样本外。</p>';}},
    portfolio:{title:"组合优化：风险、收益和仓位之间怎样取舍？",intro:"人工年化预期收益 A=8%、B=12%，波动率 A=20%、B=30%；现金收益为零，不做空、不加杠杆。",
      controls:[control("rho","两资产相关系数",-1,1,.1,.2),control("gamma","方差风险惩罚 λ",0,10,.5,2),control("cap","单只资产权重上限（%）",0,100,10,70)],
      render:v=>{const r=portfolio(v.rho,v.gamma,v.cap/100),b=r.best;return metrics([["A / B / 现金",pct(b.a)+" / "+pct(b.b)+" / "+pct(b.cash)],["预期收益",pct(b.ret)],["组合波动",pct(b.risk)],["目标值",fmt(b.objective,4)]])+plot({dots:[{name:"可行权重网格",color:colors.ink,radius:1.8,opacity:.3,points:r.points.map(p=>[100*p.risk,100*p.ret])},{name:"当前目标最优",color:colors.b,radius:6,points:[[100*b.risk,100*b.ret]]}],series:[{name:"网格非支配边界",color:colors.a,points:r.frontier.map(p=>[100*p.risk,100*p.ret])}],xd:[0,31],yd:[0,12.5],xlabel:"年化波动（%）",ylabel:"人工预期收益（%）"})+'<p>遍历 2 个百分点的权重网格，最大化预期收益 − λ × 方差。边界仅代表当前离散网格，不是连续最优证明；不含交易费用或真实收益预测。</p>';}}
  };
  function mount(container){
    for(const target of container.querySelectorAll("[data-lesson-lab]")){
      const lab=labs[target.dataset.lessonLab];
      if(!lab||target.dataset.ready)continue;
      target.dataset.ready="true";
      target.className="mathlab";
      target.innerHTML='<div class="mathlab-tag">动手实验 · 人工数据</div><h4>'+lab.title+'</h4><p>'+lab.intro+'</p><div class="mathlab-controls">'+lab.controls.map(c=>'<label><span>'+c.label+' <output></output></span><input type="range" data-key="'+c.key+'" min="'+c.min+'" max="'+c.max+'" step="'+c.step+'" value="'+c.value+'"></label>').join("")+'</div><button class="mathlab-reset" type="button">恢复课本参数</button><div class="mathlab-results"></div>';
      const inputs=[...target.querySelectorAll("input")],out=target.querySelector(".mathlab-results");
      function update(){
        const v={};inputs.forEach((input,i)=>{v[input.dataset.key]=Number(input.value);input.parentElement.querySelector("output").textContent=input.value;});
        out.innerHTML=lab.render(v);
      }
      inputs.forEach(i=>i.addEventListener("input",update));
      target.querySelector("button").addEventListener("click",()=>{inputs.forEach((i,j)=>i.value=lab.controls[j].value);update();});
      update();
    }
  }
  const api={bayes,moments,correlation,ridge,gradient,confidence,fitTree,predict,treeExperiment,boosting,portfolio,labs,mount};
  root.QuantMathLab=api;
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof self!=="undefined"?self:globalThis);
