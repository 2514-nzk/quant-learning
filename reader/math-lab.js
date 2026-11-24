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

  // Factor research: small deterministic synthetic fixtures, not a market backtest.
  function averageRanks(values){
    const order=values.map((_,i)=>i).sort((a,b)=>values[b]-values[a]||a-b),out=[];
    for(let i=0;i<order.length;){
      let j=i+1;while(j<order.length&&values[order[j]]===values[order[i]])j++;
      for(let k=i;k<j;k++)out[order[k]]=(i+j+1)/2;
      i=j;
    }
    return out;
  }
  function rankIC(x,y){
    if(x.length!==y.length||x.length<2||[...x,...y].some(v=>!Number.isFinite(v)))return null;
    return moments(averageRanks(x),averageRanks(y)).rho;
  }
  function rankingExample(swaps,ties){
    const scores=[4,3,2,1],returns=[4,3,2,1];
    for(const i of [0,1,2,0,1,0].slice(0,swaps))[returns[i],returns[i+1]]=[returns[i+1],returns[i]];
    if(ties===1)scores[0]=scores[1]=3.5;
    if(ties===2)scores.fill(1);
    return {scores,returns,scoreRanks:averageRanks(scores),returnRanks:averageRanks(returns),ic:rankIC(scores,returns)};
  }
  function icSummary(values){
    const valid=values.filter(Number.isFinite),n=valid.length;
    const avg=n?mean(valid):null,sd=n>1?(valid.every(v=>v===valid[0])?0:Math.sqrt(valid.reduce((a,b)=>a+(b-avg)**2,0)/(n-1))):null;
    return {n,total:values.length,avg,sd,icir:sd?avg/sd:null,positive:n?valid.filter(v=>v>0).length/n:null};
  }
  function icExample(avg,scale,missing){
    const base=[.12,-.04,.06,.02,.09];
    return base.map((v,i)=>i>=5-missing?null:avg+(v-.05)*scale);
  }
  function quartiles(market,slope,missing,direction=1){
    const rows=Array.from({length:12},(_,i)=>({code:"S"+String(i+1).padStart(2,"0"),score:direction*(i+1),
      ret:missing&&i===11?null:market+slope*(Math.floor(i/3)-1.5)+[-.004,0,.004][i%3]}));
    const sorted=[...rows].sort((a,b)=>a.score-b.score||a.code.localeCompare(b.code));
    const groups=Array.from({length:4},(_,i)=>{
      const members=sorted.slice(i*3,i*3+3);
      return {members,ret:members.every(r=>Number.isFinite(r.ret))?mean(members.map(r=>r.ret)):null};
    });
    const valid=rows.filter(r=>Number.isFinite(r.ret)),top=groups[3].ret,bottom=groups[0].ret;
    return {rows,groups,coverage:valid.length/rows.length,ic:rankIC(valid.map(r=>r.score),valid.map(r=>r.ret)),
      spread:top===null||bottom===null?null:top-bottom,
      benchmark:valid.length===rows.length?mean(valid.map(r=>r.ret)):null,
      excess:top!==null&&valid.length===rows.length?top-mean(valid.map(r=>r.ret)):null};
  }
  function neutralExample(industry,size,mode){
    // FWL: industry demeaning then common within-industry log-size regression.
    const rows=Array.from({length:9},(_,i)=>{
      const g=Math.floor(i/3),k=i%3,logSize=2+g*.5+k;
      return {code:"S"+(i+1),g,logSize,raw:(g-1)*industry+size*logSize+[.4,-.8,.4][k]};
    });
    for(const r of rows){
      const group=rows.filter(q=>q.g===r.g);
      r.z=r.raw-mean(group.map(q=>q.raw));r.x=r.logSize-mean(group.map(q=>q.logSize));
    }
    const denom=rows.reduce((s,r)=>s+r.x*r.x,0);
    const beta=rows.reduce((s,r)=>s+r.x*r.z,0)/denom;
    for(const r of rows){r.residual=r.z-beta*r.x;r.output=[r.raw,r.z,r.residual][mode];}
    return {rows,beta,groupMeans:[0,1,2].map(g=>mean(rows.filter(r=>r.g===g).map(r=>r.output))),
      sizeDot:rows.reduce((s,r)=>s+r.x*r.output,0)};
  }
  function rng(seed){
    let state=seed>>>0;
    return ()=>{state=(Math.imul(1664525,state)+1013904223)>>>0;return state/4294967296;};
  }
  function arSample(phi,n=60){
    const random=rng(20261124),out=[];let x=0;
    for(let i=0;i<n+80;i++){
      x=phi*x+.08*(2*random()-1);
      if(i>=80)out.push(.05+x);
    }
    return out;
  }
  function hac(series,lags){
    const n=series.length,avg=mean(series),u=series.map(x=>x-avg);
    const ac=Array.from({length:lags+1},(_,k)=>u.slice(k).reduce((s,v,i)=>s+v*u[i],0)/n);
    const weights=ac.map((v,k)=>k===0?1:1-k/(lags+1));
    const longRun=ac.reduce((s,v,k)=>s+v*weights[k]*(k===0?1:2),0);
    const iid=Math.sqrt(ac[0]/(n-1));
    const se=Math.sqrt(Math.max(0,longRun)/n);
    return {avg,iid,se,ac,weights,low:avg-1.96*se,high:avg+1.96*se,
      lag1:ac[0]?u.slice(1).reduce((s,v,i)=>s+v*u[i],0)/(n*ac[0]):null};
  }
  function quantile(sorted,p){
    const j=(sorted.length-1)*p,i=Math.floor(j);return sorted[i]+(j-i)*(sorted[Math.min(i+1,sorted.length-1)]-sorted[i]);
  }
  function blockBootstrap(series,block,reps=600){
    const random=rng(731),n=series.length,means=[],first=[];
    for(let i=0;i<reps;i++){
      const indices=[];
      while(indices.length<n){
        const start=Math.floor(random()*n);
        for(let k=0;k<block&&indices.length<n;k++)indices.push((start+k)%n);
      }
      if(i===0)first.push(...indices);
      means.push(mean(indices.map(j=>series[j])));
    }
    means.sort((a,b)=>a-b);
    return {means,first,low:quantile(means,.025),high:quantile(means,.975)};
  }
  function holm(p){
    const order=p.map((v,i)=>({v,i})).sort((a,b)=>a.v-b.v||a.i-b.i),adjusted=[];let prev=0;
    order.forEach((r,i)=>{prev=Math.min(1,Math.max(prev,(p.length-i)*r.v));adjusted[r.i]=prev;});
    return adjusted;
  }
  function purgeRows(rows,cutoff,gap){
    return rows.filter(r=>r.signal<cutoff).map(r=>({...r,allowed:r.available+gap<cutoff}));
  }
  function timeline(horizon,delay){
    return Array.from({length:24},(_,i)=>{
      const signal=i*5,entry=signal+1,end=entry+horizon,available=end+delay;
      const x=[-2,-1,0,1,2,1,-1,2][i%8];
      const y=(i<12?.03:-.03)*x+[.005,-.008,.003,-.002][i%4];
      return {signal,entry,end,available,x,y};
    });
  }
  function fitOne(rows){
    if(rows.length<2)return null;
    const m=moments(rows.map(r=>r.x),rows.map(r=>r.y));
    if(!m.varx)return null;
    const slope=m.cov/m.varx;
    return {slope,intercept:m.my-slope*m.mx};
  }
  function rollingAt(rows,cutoff,gap,window){
    const candidates=purgeRows(rows,cutoff,gap);
    const allowed=candidates.filter(r=>r.allowed).slice(-window),naive=candidates.slice(-window);
    const current=rows.find(r=>r.signal===cutoff),valid=fitOne(allowed),leaky=fitOne(naive);
    const prediction=model=>model&&current?model.intercept+model.slope*current.x:null;
    return {allowed,naive,valid,leaky,current,strictPrediction:prediction(valid),naivePrediction:prediction(leaky),
      leaked:naive.filter(r=>!r.allowed).length};
  }
  const table=(headers,rows)=>'<div class="risk-capacity"><table><thead><tr>'+headers.map(v=>'<th>'+v+'</th>').join("")+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(v=>'<td>'+v+'</td>').join("")+'</tr>').join("")+'</tbody></table></div>';
  const seriesPlot=values=>plot({series:[{name:"人工时间序列",color:colors.a,points:values.map((v,i)=>[i+1,v])},{name:"均值",color:colors.ink,points:[[1,mean(values)],[values.length,mean(values)]]}],xlabel:"观察期",ylabel:"人工 IC"});
  Object.assign(labs,{
    rankic:{title:"RankIC：两份排行榜到底有多相似？",intro:"使用四只抽象股票。通过相邻交换改变未来收益排序，再试并列因子值。",
      controls:[control("swaps","相邻交换次数",0,6,1,1),control("ties","因子并列（0 无 / 1 前两只 / 2 全部）",0,2,1,0)],
      render:v=>{const r=rankingExample(v.swaps,v.ties);return metrics([["Spearman RankIC",fmt(r.ic)],["股票数量","4"]])+table(["股票","因子分","未来收益（人工单位）","因子名次","收益名次"],r.scores.map((x,i)=>["ABCD"[i],fmt(x,1),r.returns[i],r.scoreRanks[i],r.returnRanks[i]]))+plot({dots:[{name:"股票名次配对",color:colors.a,points:xy(r.scoreRanks,r.returnRanks)}],xd:[.5,4.5],yd:[.5,4.5],xlabel:"因子名次（1 最高）",ylabel:"收益名次（1 最高）"})+'<p>有并列时取平均秩；恒定因子相关未定义。交换名次不是改变真实市场收益。</p>';}},
    icir:{title:"平均 IC 与 ICIR：均值一样，稳定性可能不同",intro:"以课本五期 IC 为起点，改变中心、围绕中心的波动，或让末尾若干期缺失。",
      controls:[control("avg","五期目标中心",-.1,.15,.01,.05),control("scale","波动倍数",0,2,.1,1),control("missing","缺失期数",0,4,1,0)],
      render:v=>{const x=icExample(v.avg,v.scale,v.missing),r=icSummary(x);return metrics([["样本平均 IC",fmt(r.avg)],["样本标准差",fmt(r.sd,4)],["未年化 ICIR",fmt(r.icir)],["有效期 / 总期",r.n+" / "+r.total],["正 IC 比例",pct(r.positive)]])+table(["期次","RankIC"],x.map((q,i)=>[i+1,fmt(q)]))+plot({dots:[{name:"有效 IC",color:colors.a,points:x.map((q,i)=>[i+1,q]).filter(p=>Number.isFinite(p[1]))}],xd:[.5,5.5],yd:[-.35,.35],xlabel:"观察期",ylabel:"RankIC"})+'<p>标准差用 n−1；缺失不是零。只有一期或波动为零时 ICIR 未定义。改变缺失会改变实际样本均值。</p>';}},
    quartiles:{title:"四分组：因子价差为正，多头仍会亏吗？",intro:"12 只人工股票，按分数分四组，每组三只。改变市场整体收益与因子收益梯度。",
      controls:[control("market","整体收益中心（%）",-10,10,1,-5),control("slope","相邻组收益差（百分点）",-4,4,.5,2),control("missing","最高原始分股票标签缺失（0/1）",0,1,1,0),control("direction","因子方向（-1 反向 / +1 正向）",-1,1,2,1)],
      render:v=>{const r=quartiles(v.market/100,v.slope/100,v.missing,v.direction);
        const values=r.groups.map(g=>g.ret===null?null:g.ret*100);
        return metrics([["Q4 多头毛收益",pct(r.groups[3].ret)],["Q4−Q1 价差",r.spread===null?"未定义":fmt(100*r.spread,2)+" 个百分点"],["四组全体等权",pct(r.benchmark)],["Q4 相对等权",pct(r.excess)],["标签覆盖率",pct(r.coverage)],["可比较 RankIC",fmt(r.ic)]])+table(["组别","股票","毛收益"],r.groups.map((g,i)=>["Q"+(i+1),g.members.map(q=>q.code).join("、"),pct(g.ret)]))+plot({series:[{name:"零收益线",color:colors.ink,points:[[1,0],[4,0]]}],dots:[{name:"各组收益",color:colors.a,points:values.map((q,i)=>[i+1,q]).filter(p=>Number.isFinite(p[1]))}],xd:[.5,4.5],yd:[-17,17],xlabel:"分组 Q1–Q4",ylabel:"毛收益（%）"})+'<p>缺失标签的组和完整等权基准不输出收益，不填零、不悄悄换权；价差不是可直接交易的多空收益。</p>';}},
    neutral:{title:"行业与规模中性化：到底减掉了什么？",intro:"九只人工股票、三个行业，先去行业均值，再对组内对数市值拟合共用斜率。",
      controls:[control("industry","行业偏移强度",0,4,.5,2),control("size","规模暴露强度",0,2,.25,1),control("mode","处理步骤（0 原始 / 1 行业 / 2 行业+规模）",0,2,1,2)],
      render:v=>{const r=neutralExample(v.industry,v.size,v.mode);return metrics([["组内规模回归斜率",fmt(r.beta)],["当前分数与组内规模内积",fmt(r.sizeDot)],["当前三个行业平均分",r.groupMeans.map(x=>fmt(x,2)).join(" / ")]])+table(["股票","行业","对数市值","原始因子","组内去均值","最终残差"],r.rows.map(q=>[q.code,q.g+1,fmt(q.logSize,1),fmt(q.raw,2),fmt(q.z,2),fmt(q.residual,2)]))+plot({dots:[{name:"原始因子",color:colors.ink,points:r.rows.map(q=>[q.logSize,q.raw])},{name:"当前处理后因子",color:colors.a,points:r.rows.map(q=>[q.logSize,q.output])}],xlabel:"对数市值",ylabel:"因子分数"})+'<p>残差在本截面与行业哑变量、组内规模线性正交；并不保证组合行业权重为零或没有风险。</p>';}},
    hac:{title:"HAC：时间依赖如何改变均值的标准误？",intro:"固定扰动序列，改变 AR(1) 系数与 Bartlett 截断滞后 L。60 期人工序列。",
      controls:[control("phi","AR(1) 系数 φ",-.8,.8,.1,.6),control("lags","HAC 滞后 L",0,12,1,4)],
      render:v=>{const x=arSample(v.phi),r=hac(x,v.lags);return metrics([["样本平均",fmt(r.avg,4)],["样本一阶自相关",fmt(r.lag1)],["IID 标准误",fmt(r.iid,4)],["HAC 标准误",fmt(r.se,4)],["HAC 正态近似区间","["+fmt(r.low,4)+", "+fmt(r.high,4)+"]"]])+seriesPlot(x)+table(["滞后","自协方差（分母 T）","Bartlett 权重"],r.ac.map((a,k)=>[k,fmt(a,6),fmt(r.weights[k],3)]))+'<p>IID 使用样本标准差；HAC 的自协方差分母是 T，L=0 不必与 IID 完全相等。HAC 也可能更小；区间只是弱依赖条件下的正态近似，不代表真实 Alpha。</p>';}},
    bootstrap:{title:"区块 Bootstrap：为什么不把时间顺序打散？",intro:"使用同一 60 期固定人工 AR(1) 序列。对照逐期抽取和循环区块抽样，各 600 次。",
      controls:[control("phi","AR(1) 系数 φ",-.8,.8,.1,.6),control("block","区块长度 B",1,20,1,8)],
      render:v=>{const x=arSample(v.phi),a=blockBootstrap(x,1),b=blockBootstrap(x,v.block);
        const interval=r=>"["+fmt(r.low,4)+", "+fmt(r.high,4)+"]";
        const lo=Math.min(a.low,b.low,mean(x))-.03,hi=Math.max(a.high,b.high,mean(x))+.03;
        return metrics([["逐期重采样 95% 区间",interval(a)],["区块重采样 95% 区间",interval(b)],["区块区间宽度",fmt(b.high-b.low,4)]])+plot({series:[{name:"逐期抽样",color:colors.ink,points:[[a.low,1],[a.high,1]]},{name:"区块抽样",color:colors.a,points:[[b.low,2],[b.high,2]]}],dots:[{name:"原样本均值",color:colors.b,points:[[mean(x),1],[mean(x),2]]}],xd:[lo,hi],yd:[.5,2.5],xlabel:"重采样均值",ylabel:"方法（1 / 2）"})+'<p>第一个区块样本的前 20 个原始期号：'+b.first.slice(0,20).map(i=>i+1).join(" → ")+'。抽到末尾会循环回起点，拼到 60 期后截断。块长为 1 时两种方法完全相同；块长不是通过最有利区间事后挑选。</p>';}},
    holm:{title:"多重检验：试得越多，原来的 p 值还算数吗？",intro:"固定人工 p 值序列，比较未经调整与 Holm 调整；默认复现课本三个假设。",
      controls:[control("first","第一个原始 p 值",.001,.1,.001,.01),control("n","事先定义的假设族大小",3,12,1,3),control("alpha","显著性阈值 α（%）",1,10,1,5)],
      render:v=>{const p=[v.first,.03,.08,.04,.06,.015,.2,.1,.11,.045,.3,.6].slice(0,v.n),q=holm(p),alpha=v.alpha/100;
        return metrics([["未经调整达到阈值",p.filter(x=>x<=alpha).length],["Holm 后达到阈值",q.filter(x=>x<=alpha).length]])+table(["假设","原始 p","Holm 调整 p","调整后拒绝 H₀？"],p.map((x,i)=>["H"+(i+1),fmt(x,3),fmt(q[i],3),q[i]<=alpha?"是":"否"]))+'<p>先排序、乘剩余比较数、取累积最大值并截断到 1，再还原原顺序。这里 p 值是给定的，不是市场数据算出的；Holm 要求原始 p 值有效且假设族事先定义。</p>';}},
    purge:{title:"Purge：信号早于验证，不代表答案已经知道",intro:"每 5 个模拟时段产生信号，次时段入场。标签退出后还需要等待数据可用。",
      controls:[control("cutoff","验证首信号时段",20,100,5,40),control("horizon","入场后持有时段",1,15,1,5),control("delay","退出后标签延迟",0,5,1,0),control("gap","额外安全间隔",0,5,1,0)],
      render:v=>{const rows=purgeRows(timeline(v.horizon,v.delay),v.cutoff,v.gap),ok=rows.filter(r=>r.allowed).length;return metrics([["历史候选",rows.length],["训练准入",ok],["清除",rows.length-ok]])+table(["信号","入场","退出","标签可用","可用+间隔","准入？"],rows.slice(-12).map(r=>[r.signal,r.entry,r.end,r.available,r.available+v.gap,r.allowed?"保留":"清除"]))+'<p>表格显示最近最多 12 条候选，统计包含全部候选。仅当 label_available + gap 严格早于验证信号才保留；相等也清除。这是前向 Purge，不是通用 Embargo。</p>';}},
    rolling:{title:"滚动训练：如果提前看了下一周标签，会发生什么？",intro:"固定一维人工因子，后半段人为反转收益关系。对照严格前向训练与故意只按信号日期筛选的泄漏版本。",
      controls:[control("cutoff","当前信号时段",40,115,5,75),control("horizon","持有时段",1,15,1,5),control("delay","标签延迟",0,5,1,0),control("window","最多训练记录数",4,12,1,8)],
      render:v=>{const rows=timeline(v.horizon,v.delay),r=rollingAt(rows,v.cutoff,0,v.window);
        const history=rows.filter(q=>q.signal>=40&&q.signal<=v.cutoff).map(q=>({t:q.signal,...rollingAt(rows,q.signal,0,v.window)}));
        const points=key=>history.map(q=>[q.t,q[key]]).filter(p=>Number.isFinite(p[1]));
        return metrics([["严格预测",fmt(r.strictPrediction,4)],["错误版本预测",fmt(r.naivePrediction,4)],["严格训练记录",r.allowed.length],["错误版本提前读到的标签",r.leaked]])+table(["历史信号","标签可用","严格模型训练","错误版本训练"],rows.filter(q=>q.signal<v.cutoff).slice(-14).map(q=>[q.signal,q.available,r.allowed.some(a=>a.signal===q.signal)?"是":"否",r.naive.some(a=>a.signal===q.signal)?(q.available>=v.cutoff?"泄漏":"是"):"否"]))+
        (history.length>1?plot({series:[{name:"严格前向",color:colors.a,points:points("strictPrediction")},{name:"错误信号日期筛选",color:colors.warn,points:points("naivePrediction")}],xlabel:"信号时段",ylabel:"人工预测收益"}):"")+'<p>每期重新拟合带截距的一元回归，最多使用指定条数的历史记录。错误版本仅作反例，不是候选策略。预测差异不代表收益改善；持有期滑块仅改变人工标签可用时间，不重新模拟真实持有期收益。</p>';}}
  });

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
  const api={bayes,moments,correlation,ridge,gradient,confidence,fitTree,predict,treeExperiment,boosting,portfolio,averageRanks,rankIC,rankingExample,icSummary,icExample,quartiles,neutralExample,arSample,hac,blockBootstrap,holm,purgeRows,timeline,rollingAt,labs,mount};
  root.QuantMathLab=api;
  if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof self!=="undefined"?self:globalThis);
