const {chromium}=require('playwright');const fs=require('fs');
(async()=>{
 const [,, outDir, mode, tArg]=process.argv;
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
 await p.goto('file://'+process.cwd()+'/overlay.html');await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(500);
 fs.mkdirSync(outDir,{recursive:true});
 const times = mode==='one'?[parseFloat(tArg)]:Array.from({length:540},(_,i)=>i/30);
 for(const [i,t] of times.entries()){
   await p.evaluate(t=>render(t),t);
   const name = mode==='one'?`${outDir}/t_${t}.png`:`${outDir}/o_${String(i).padStart(4,'0')}.png`;
   await p.screenshot({path:name,omitBackground:true});
 }
 await b.close();
})();
