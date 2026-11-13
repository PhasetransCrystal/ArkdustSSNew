// SSCG-V1: Yf main plot, sigma and normalized-envelope side-by-side insets.
// node tools/plot-sscg-profile.mjs [--check-only] [--out path]
// Baseline environment only: Ih=100, Lf=0, Delta=0, sigma_o=sigma0.
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const here=dirname(fileURLToPath(import.meta.url));
const theme=JSON.parse(readFileSync(resolve(here,'hume-chart-theme.json'),'utf8'));
const args=process.argv.slice(2), oi=args.indexOf('--out');
if(oi>=0&&!args[oi+1]) throw new Error('--out requires a path');
const out=oi>=0?resolve(args[oi+1]):resolve(here,'../其它/引用图像/休谟与深度/SSCG-V1-变焦空间分布.svg');
const sigma0=0.4;
const profiles=[
  {name:'内域模拟',yc:18,color:theme.curves.primary.color,dash:''},
  {name:'外域模拟',yc:55,color:theme.curves.secondary.color,dash:theme.curves.dasharray.dash},
].map(p=>({...p,sc:sigma0*100/p.yc,re:10*Math.sqrt(p.yc/100),rw:10*Math.sqrt(p.yc/100)*(500/(p.yc*(95-p.yc)))**0.25}));
const sigma=(p,x)=>sigma0+(p.sc-sigma0)/(1+(x/p.re)**4);
const yf=(p,x)=>100*sigma0/sigma(p,x);
const normalized=u=>1/(1+u**4);
const near=(a,b,t=1e-10)=>assert.ok(Math.abs(a-b)<t,`${a} != ${b}`);
for(const p of profiles){
  near(sigma(p,0),p.sc); near(yf(p,0),p.yc);
  near(sigma(p,p.re),(p.sc+sigma0)/2);
  near(yf(p,p.rw),p.yc+5);
  near(yf(p,1e6),100); near(sigma(p,1e6),sigma0);
  let last=p.yc;
  for(let x=.05;x<=20;x+=.05){
    assert.ok(yf(p,x)>last); last=yf(p,x);
    near(sigma(p,x),sigma(p,-x));
    near((sigma(p,x)-sigma0)/(p.sc-sigma0),normalized(x/p.re));
    near(yf(p,x),100*(1+(x/p.re)**4)/(100/p.yc+(x/p.re)**4));
  }
  const tail=1e3;
  near((sigma(p,tail)-sigma0)/((p.sc-sigma0)*(p.re/tail)**4),1,1e-5);
  console.log(`${p.name}: sigma_c=${p.sc.toFixed(6)}, Reff=${p.re.toFixed(6)}, Rwork=${p.rw.toFixed(6)}, Yf(Rwork)=${yf(p,p.rw).toFixed(6)}`);
}
console.log('PASS: center, half-increment, symmetry, monotonicity, far field, normalization, Yf identity, working boundary');
if(args.includes('--check-only')) process.exit(0);
const W=1280,H=966, parts=[];
const ink=theme.font.default_fill, muted=theme.palette.legend_metric;
const n=v=>String(Math.round(v*100)/100);
const sub=v=>`<tspan baseline-shift="sub" font-size="75%">${v}</tspan>`;
const sup=v=>`<tspan baseline-shift="super" font-size="75%">${v}</tspan>`;
const YF=`Y${sub('f')}`, SM=`σ${sub('m')}`, S0=`σ${sub('0')}`, SC=`σ${sub('c')}`, RE=`R${sub('eff')}`, RW=`R${sub('work')}`;
function text(x,y,s,size=14,fill=ink,anchor='start',extra=''){
 parts.push(`<text x="${n(x)}" y="${n(y)}" font-size="${size}" fill="${fill}" text-anchor="${anchor}" ${extra}>${s}</text>`);
}
function line(x1,y1,x2,y2,color=theme.baseline.color,width=1.3,dash='5 5'){
 parts.push(`<path d="M${n(x1)} ${n(y1)}L${n(x2)} ${n(y2)}" fill="none" stroke="${color}" stroke-width="${width}" ${dash?`stroke-dasharray="${dash}"`:''}/>`);
}
function dot(x,y,color){parts.push(`<circle cx="${n(x)}" cy="${n(y)}" r="4" fill="${color}" stroke="white" stroke-width="1.5"/>`);}
function frame(id,l,t,w,h,xmin,xmax,ymin,ymax){return {id,l,t,w,h,xmin,xmax,ymin,ymax,r:l+w,b:t+h,X:x=>l+(x-xmin)/(xmax-xmin)*w,Y:y=>t+h-(y-ymin)/(ymax-ymin)*h};}
const M=frame('main',90,170,1100,330,0,20,0,110);
const S=frame('sigma',90,685,495,185,-20,20,0,2.5);
const Z=frame('normalized',695,685,495,185,-3,3,0,1.1);
function grid(f,xs,ys){for(const x of xs)line(f.X(x),f.t,f.X(x),f.b,theme.grid.stroke,theme.grid.width,'');for(const y of ys)line(f.l,f.Y(y),f.r,f.Y(y),theme.grid.stroke,theme.grid.width,'');}
function axes(f,xs,ys,xlabel){
 line(f.l,f.t,f.l,f.b,theme.axes.color,theme.axes.width,'');line(f.l,f.b,f.r,f.b,theme.axes.color,theme.axes.width,'');
 for(const x of xs){line(f.X(x),f.b,f.X(x),f.b+6,theme.axes.color,1.5,'');text(f.X(x),f.b+22,String(x),12,ink,'middle');}
 for(const y of ys){line(f.l-6,f.Y(y),f.l,f.Y(y),theme.axes.color,1.5,'');text(f.l-12,f.Y(y)+4,String(y),12,ink,'end');}
 text((f.l+f.r)/2,f.b+44,xlabel,14,ink,'middle');
}
function curve(f,fn,color,dash=''){
 const pts=Array.from({length:1001},(_,i)=>{const x=f.xmin+(f.xmax-f.xmin)*i/1000;return `${i?'L':'M'}${n(f.X(x))} ${n(f.Y(fn(x)))}`;});
 parts.push(`<path clip-path="url(#${f.id})" d="${pts.join('')}" fill="none" stroke="${color}" stroke-width="${theme.curves.default_width}" stroke-linejoin="round" ${dash?`stroke-dasharray="${dash}"`:''}/>`);
}
// Same palette and typographic hierarchy as the original plotter, with a legible separated subtitle.
text(W/2,60,'SSCG-V1 · 表征休谟空间分布',40,ink,'middle','font-weight="900" stroke="white" stroke-width="7" paint-order="stroke fill"');
text(W/2,94,'标准整定 · 中心低表征休谟，远场回归基准现实',20,theme.curves.secondary.color,'middle');
text(90,120,`${YF}(x) = 100 · ${S0} / ${SM}(x) = 100 · [1 + (x/${RE})${sup('4')}] / [100/Y${sub('c')} + (x/${RE})${sup('4')}]`,15);
text(1190,130,'Ih = 100 · Lf = 0 · Δ = 0',14,muted,'end');
text(M.l,M.t-14,`A / ${YF} — 径向距离`,16,ink,'start','font-weight="700"');
const mx=[0,2,4,6,8,10,12,14,16,18,20],my=[0,20,40,60,80,100];
grid(M,mx,my);
for(const p of profiles){
 parts.push(`<rect x="${M.l}" y="${n(M.Y(p.yc+5))}" width="${n(M.X(p.rw)-M.l)}" height="${n(M.Y(p.yc-5)-M.Y(p.yc+5))}" fill="${p.color}" fill-opacity="0.15"/>`);
 line(M.l,M.Y(p.yc+5),M.X(p.rw),M.Y(p.yc+5),p.color,1,'3 4');
 line(M.X(p.rw),M.Y(p.yc+5),M.X(p.rw),M.b,p.color,1.3,'3 4');
}
line(M.l,M.Y(100),M.r,M.Y(100));
for(const p of [...profiles].reverse())curve(M,x=>yf(p,x),p.color,p.dash);
axes(M,mx,my,'径向距离 x（m） · x = 0 为机器中心');
text(M.r-6,M.Y(100)-8,'远场基准 Yf = 100',12,theme.baseline.label.fill,'end');
for(const p of profiles){
 dot(M.l,M.Y(p.yc),p.color);dot(M.X(p.rw),M.Y(p.yc+5),p.color);
 text(M.X(.25),M.Y(p.yc)-10,`中心 ${p.yc}`,13,p.color);
 const tx=M.X(p.rw)+34,ty=M.Y(p.yc+5)+35;
 line(M.X(p.rw)+5,M.Y(p.yc+5)+4,tx-8,ty-5,p.color,1,'');
 text(tx,ty,`${RW} = ${p.rw.toFixed(2)} m；${YF} = ${p.yc+5}`,15,ink);
}
// Legend and explicit model assumptions; no implication that sigma0 is an arithmetic midpoint.
profiles.forEach((p,i)=>{
 const x=90+i*565;
 line(x,569,x+30,569,p.color,2.5,p.dash);
 text(x+42,574,`${p.name} · Yc = Yt = ${p.yc} · 容差 ±5`,16);
 text(x+42,599,`${SC} = ${p.sc.toFixed(3)}，${RE} = ${p.re.toFixed(2)} m，${RW} = ${p.rw.toFixed(2)} m`,14,muted);
});
text(90,626,'浅色框：目标容差与理想工作范围的交集；未扣除机身死区。两条曲线代表两种独立工况。',13,muted);
text(S.l,657,`B / 变焦包络 ${SM} — 空间截面`,17,ink,'start','font-weight="700"');
text(Z.l,657,'C / 归一化包络 — 两工况共用形状',17,ink,'start','font-weight="700"');
const sx=[-20,-10,0,10,20],sy=[0,.5,1,1.5,2,2.5];
grid(S,sx,sy);line(S.l,S.Y(sigma0),S.r,S.Y(sigma0));
for(const p of [...profiles].reverse()){
 curve(S,s=>sigma(p,Math.abs(s)),p.color,p.dash);
 for(const sign of [-1,1])dot(S.X(sign*p.re),S.Y((p.sc+sigma0)/2),p.color);
}
axes(S,sx,sy,'截面位置 s（m），径向距离 x = |s|');
text(S.r-6,S.Y(sigma0)-8,'σ0 = 0.40',11,muted,'end');
const zx=[-3,-2,-1,0,1,2,3],zy=[0,.25,.5,.75,1];
grid(Z,zx,zy);line(Z.l,Z.Y(.5),Z.r,Z.Y(.5));
curve(Z,normalized,profiles[0].color);
for(const u of [-1,1]){line(Z.X(u),Z.Y(.5),Z.X(u),Z.b);dot(Z.X(u),Z.Y(.5),profiles[0].color);}
axes(Z,zx,zy,`u = s / ${RE}；z = (${SM} − ${S0}) / (${SC} − ${S0})`);
text(Z.X(0),Z.Y(.22),'z = 1 / (1 + u⁴)',14,muted,'middle');
text(S.l,947,`圆点：x = ${RE}，失焦增量减半；非拐点、非工作边界。`,12,muted);
text(Z.l,947,'u = ±1 时 z = 0.5；归一化后隐藏了高度和实际距离差异。',12,muted);
const defs=[M,S,Z].map(f=>`<clipPath id="${f.id}"><rect x="${f.l}" y="${f.t}" width="${f.w}" height="${f.h}"/></clipPath>`).join('');
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="title desc"><title id="title">SSCG-V1 表征休谟与距离</title><desc id="desc">上方主图为基准背景下两组标准整定的Yf径向分布，中心值18和55，工作边界为23和60。下方并排展示sigma空间截面和归一化包络。所有工况Ih=100，不代表真实塌缩的完整频谱。</desc><defs>${defs}</defs><rect width="100%" height="100%" fill="${theme.canvas.background.value}"/><g font-family="${theme.font.family}" fill="${ink}">${parts.join('\n')}</g></svg>\n`;
mkdirSync(dirname(out),{recursive:true});writeFileSync(out,svg,'utf8');console.log(`Written ${out} (${W}x${H})`);
