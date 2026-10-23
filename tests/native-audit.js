/* QA only: native render-state and exported-raster inspection. No application
 * state is exposed by the production navigator for browser automation. */
'use strict';
const statusNode = document.getElementById('status');
const resultsNode = document.getElementById('results');
const v = CpossVisualization;
let host, app, report, currentErrors = [], html;
const frame = document.getElementById('viewer');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
function showReport() {
    const text = JSON.stringify(report, null, 2);
    document.getElementById('report-json').textContent = text;
    const a = document.getElementById('download');
    if (a.href.startsWith('blob:')) URL.revokeObjectURL(a.href);
    a.href = URL.createObjectURL(new Blob([text], {type: 'application/json'})); a.hidden = false;
}
async function initialize() {
    html ??= await (await fetch('../index.html', {cache:'no-store'})).text();
    const loaded = new Promise(resolve => frame.onload = resolve);
    frame.srcdoc = html.replace('<head>', '<head><base href="'+new URL('../', location.href).href+'">')
        .replace(/<script src="assets\/navigator\.js[^>]*><\/script>/, '')
        .replace('<body>', '<body><script id="standalone-json-data" type="application/json"></scr'+'ipt>');
    await loaded;
    host = frame.contentWindow;
    host.addEventListener('error', event => currentErrors.push(String(event.error || event.message)));
    host.addEventListener('unhandledrejection', event => currentErrors.push(String(event.reason)));
    app = new host.Chemiscope.ChemiscopeApp('chemiscope-container');
    host.CpossVisualization.install(app);
    host.document.getElementById('loading').style.display = 'none';
    host.document.querySelector('.cposs-header').style.display = 'none';
    host.document.querySelector('.footer').style.display = 'none';
    host.document.documentElement.style.setProperty('--header-height', '0px');
    host.document.documentElement.style.setProperty('--footer-height', '0px');
}
function releasePrevious() {
    // Dispose WebGL contexts in the QA batch before removing native DOM nodes.
    // Reloading the iframe periodically also releases native event listeners.
    for (const canvas of host.document.querySelectorAll('canvas')) {
        for (const kind of ['webgl2','webgl','experimental-webgl']) {
            try { const context = canvas.getContext(kind); if (context) { context.getExtension('WEBGL_lose_context')?.loseContext(); break; } } catch (_) { /* other canvas type */ }
        }
    }
}
async function load(source, first) {
    currentErrors = [];
    releasePrevious();
    const data = v.copy(source);
    delete data.auditFirstStructure;
    await app.load(first ? {loadStructure: async index => { if(index !== 0) throw new Error('Audit loads original first geometry only'); return v.copy(first); }} : {}, data);
    await app.visualizer.map._restyleFull();
    await delay(90);
    return app.visualizer;
}
function inspect(source, visualizer) {
    const prepared = v.prepare(source), map = visualizer.map, settings = visualizer.saveSettings();
    const errors = [], expected = prepared.settings;
    for (const key of ['x','y','z','color','size']) for (const [name, value] of Object.entries(expected.map[key])) {
        if (settings.map[key][name] !== value) errors.push(`Settings mismatch: ${key}.${name}: ${settings.map[key][name]} vs ${value}`);
    }
    if (JSON.stringify([0,1,2].map(i=>settings.structure[0].supercell[i]))!=='[3,3,3]' || !settings.structure[0].unitCell) errors.push('Supercell/unit-cell mismatch');
    const sg = prepared.dataset.properties[expected.map.color.property].values;
    const colors = Array.from(map._plot._fullData[0].marker.color);
    if (colors.length !== sg.length) errors.push('Rendered scatter row count mismatch');
    let mismatches=0;
    for (let i=0;i<sg.length;i++) if (Number.isFinite(sg[i]) ? Math.abs(colors[i]-Math.log10(sg[i]))>1e-12 || typeof colors[i]!=='number' : colors[i]!==v.GREY) mismatches++;
    if (mismatches) errors.push(`${mismatches} incorrect rendered marker colors`);
    const coloraxis = map._plot._fullLayout.coloraxis;
    if(coloraxis.cmin!==0 || coloraxis.cmax!==2.37) errors.push('Rendered color-axis bounds mismatch');
    const palette = map._options.colorScale();
    if(JSON.stringify(coloraxis.colorscale)!==JSON.stringify(palette)) errors.push('Rendered palette mismatch');
    const exported = visualizer.dataset();
    if (!same(exported.properties, source.properties)) errors.push('Source property export changed');
    if (exported.structures.length !== source.structures.length) errors.push('Structure index count changed');
    const samples = {};
    sg.forEach((number,i)=>{ const key=Number.isFinite(number)?number:'unknown'; if(!Object.hasOwn(samples,key)) samples[key]= {transformed:colors[i], rgb: Number.isFinite(number) ? map._options.valueToColor(colors[i],0,2.37) : v.GREY}; });
    return {settings, ...prepared.diagnostics, checkedMarkers: colors.length, colorMismatches:mismatches, samples, errors:[...errors,...currentErrors]};
}
function same(a,b) { return JSON.stringify(a,(_,x)=>typeof x==='number'&&!Number.isFinite(x)?String(x):x)===JSON.stringify(b,(_,x)=>typeof x==='number'&&!Number.isFinite(x)?String(x):x); }
function expectedRGB(number,palette) {
    if(!Number.isFinite(number))return[170,170,170];
    const t = Math.log10(number)/2.37;
    let i=0;while(i<palette.length-2&&palette[i+1][0]<t)i++;
    const [a,ca]=palette[i],[b,cb]=palette[i+1];
    const parse=s=>s.match(/\d+/g).map(Number);const x=parse(ca),y=parse(cb), f=(t-a)/(b-a);
    return x.map((value,j)=>Math.round(value+f*(y[j]-value)));
}
async function rasterSamples(source,visualizer,numbers) {
    const p=v.prepare(source),map=visualizer.map,layout=map._plot._fullLayout;
    const sg=p.dataset.properties[p.settings.map.color.property].values;
    const xs=p.dataset.properties[p.settings.map.x.property].values,ys=p.dataset.properties[p.settings.map.y.property].values;
    const points=xs.map((x,i)=>({i,x:layout.xaxis.l2p(x)+layout.xaxis._offset,y:layout.yaxis.l2p(ys[i])+layout.yaxis._offset,sg:sg[i]}));
    const width=layout.width, height=layout.height;
    const selected=[];
    for(const number of numbers){
        const candidates=points.filter(p=>Number.isNaN(number)?Number.isNaN(p.sg):p.sg===number).filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
        candidates.forEach(p=>p.clearance=Math.min(...points.filter(q=>q.i!==p.i).map(q=>Math.hypot(q.x-p.x,q.y-p.y))));
        candidates.sort((a,b)=>b.clearance-a.clearance);
        if(candidates[0])selected.push(candidates[0]);
    }
    const image = new Image(); image.src=await map.exportPNG(); await image.decode();
    const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);
    const samples=selected.map(point=>{
        const x=Math.round(point.x*image.naturalWidth/width),y=Math.round(point.y*image.naturalHeight/height);
        const rgb=Array.from(ctx.getImageData(x,y,1,1).data).slice(0,3),expected=expectedRGB(point.sg,map._options.colorScale());
        return {spaceGroup:Number.isNaN(point.sg)?'unknown':point.sg,index:point.i,clearance:point.clearance,rgb,expected,match:rgb.every((value,i)=>Math.abs(value-expected[i])<=3)};
    });
    document.getElementById('results').appendChild(image);
    return samples;
}
async function runCatalogue() {
    document.querySelectorAll('button').forEach(button=>button.disabled=true);
    report={kind:'catalogue-native',date:new Date().toISOString(),datasets:[],scope:'All original property rows and the original first structure rendered natively; all geometry rows independently validated in Python.'};
    resultsNode.textContent='';
    try {
        const manifest=await(await fetch('.audit-data/manifest.json',{cache:'no-store'})).json();
        report.sourceTree=manifest.sourceTree;
        const start=Number(new URL(location.href).searchParams.get('start')||0);
        const limit=Number(new URL(location.href).searchParams.get('limit')||manifest.datasets.length);
        const entries=manifest.datasets.slice(start,start+limit);
        const storageKey='cposs-native-audit-global-v3-'+manifest.sourceTree;
        let saved;
        try{saved=JSON.parse(localStorage.getItem(storageKey));}catch(_){}
        if(new URL(location.href).searchParams.has('fresh')){ localStorage.removeItem(storageKey); saved=null; history.replaceState(null,'',location.pathname+'?autorun=1'); }
        if(saved)report=saved;
        const completed=new Set(report.datasets.map(entry=>entry.id));
        const pending=entries.filter(entry=>!completed.has(entry.id));
        let done=report.datasets.length, batch=0;
        await initialize();
        for(const entry of pending){
            statusNode.textContent=`Rendering ${++done}/${entries.length}: ${entry.id}`;
            try{
                if(entry.error)throw new Error(entry.error);
                const source=v.parseJSON(await(await fetch('.audit-data/'+entry.file)).text());
                const visualizer=await load(source,source.auditFirstStructure);
                const record={id:entry.id,...inspect(source,visualizer)};
                report.datasets.push(record);
                if(record.errors.length)resultsNode.textContent+=entry.id+': '+record.errors.join('; ')+'\n';
            }catch(error){report.datasets.push({id:entry.id,errors:[String(error)],colorMismatches:null});resultsNode.textContent+=entry.id+': '+String(error)+'\n';}
            localStorage.setItem(storageKey,JSON.stringify(report));
            showReport();
            if(++batch===8&&done<entries.length){
                // Full document navigation releases the native renderer and all
                // WebGL/module state between small, resumable QA batches.
                location.replace(location.pathname+'?autorun=1'); return;
            }
        }
        report.summary={datasets:report.datasets.length,failures:report.datasets.filter(d=>d.errors.length).length,checkedMarkers:report.datasets.reduce((n,d)=>n+(d.checkedMarkers||0),0),colorMismatches:report.datasets.reduce((n,d)=>n+(d.colorMismatches||0),0)};
        statusNode.textContent=JSON.stringify(report.summary);statusNode.className=report.summary.failures?'fail':'pass';
    }catch(error){statusNode.textContent=String(error);report.error=String(error);}
    showReport();document.querySelectorAll('button').forEach(button=>button.disabled=false);
}
function fixture(values,settings) {
    return {meta:{name:'Native global-style regression'},structures:values.map(()=>({size:1,names:['H'],x:[0],y:[0],z:[0],cell:[4,0,0,0,4,0,0,0,4]})),properties:{'Density':{target:'structure',values:values.map((_,i)=>1+i*.1)},'Lattice Energy':{target:'structure',values:values.map((_,i)=>-40+i*5)},'Space Group':{target:'structure',values},'Experimental Info':{target:'structure',values:values.map(()=>'')}},...(settings?{settings}:{})};
}
async function runRegressions(){
    document.querySelectorAll('button').forEach(button=>button.disabled=true);resultsNode.textContent='';
    report={kind:'native-regressions',date:new Date().toISOString(),checks:[]};
    try{
        await initialize();
        const sources=[['numeric',fixture([1,2,14,230])],['reordered-symbols',fixture(['Ia-3d','P21/c','P-1','P1'])],['constant-14',fixture([14,14,14,14])],['constant-unknown',fixture(['nan','unknown',null,''])],['mixed-missing',fixture(['14','P21/c','nan',2])],['saved-style',fixture([1,2,14,230],{map:{x:{property:'Lattice Energy',scale:'log'},y:{property:'Density'},color:{property:'Density',palette:'viridis',mode:'linear',min:1,max:4},size:{property:'Density',factor:99}},structure:[{supercell:[1,1,1]}]})]];
        const referenceSamples={};
        for(const [id,source]of sources){
            statusNode.textContent='Regression: '+id;
            const visualizer=await load(source),record={id,...inspect(source,visualizer)};
            record.raster=await rasterSamples(source,visualizer,[1,2,14,230,NaN]);
            if(record.raster.some(s=>!s.match))record.errors.push('Raster RGB mismatch');
            for(const sample of record.raster){const key=sample.spaceGroup;if(referenceSamples[key]&&!same(referenceSamples[key],sample.rgb))record.errors.push('Cross-dataset RGB mismatch for '+key);else referenceSamples[key]=sample.rgb;}
            report.checks.push(record);
        }
        const manifest=await(await fetch('.audit-data/manifest.json')).json();
        for(const id of ['2aminobenzamideA','26-dichloronitrobenzeneA']){
            const entry=manifest.datasets.find(e=>e.id===id),source=v.parseJSON(await(await fetch('.audit-data/'+entry.file)).text());
            statusNode.textContent='Real dataset raster: '+id;
            const visualizer=await load(source,source.auditFirstStructure),record={id,...inspect(source,visualizer)};
            record.raster=await rasterSamples(source,visualizer,[2,4,14,19]);
            if(record.raster.some(s=>!s.match))record.errors.push('Raster RGB mismatch');
            for(const sample of record.raster)if(referenceSamples[sample.spaceGroup]&&sample.rgb.some((c,i)=>Math.abs(c-referenceSamples[sample.spaceGroup][i])>3))record.errors.push('Real-dataset RGB mismatch for '+sample.spaceGroup);
            report.checks.push(record);
        }
        // Deliberate manual imports after loading remain effective.
        app.visualizer.applySettings({map:{color:{palette:'viridis',mode:'linear',min:0,max:230},size:{factor:72}}});
        await app.visualizer.map._restyleFull();
        report.manualOverride=app.visualizer.saveSettings();
        if(report.manualOverride.map.color.palette!=='viridis'||report.manualOverride.map.size.factor!==72)throw new Error('Manual settings override failed');
        report.summary={checks:report.checks.length,failures:report.checks.filter(d=>d.errors.length).length,rasterSamples:report.checks.reduce((n,d)=>n+d.raster.length,0)};
        statusNode.textContent=JSON.stringify(report.summary);statusNode.className=report.summary.failures?'fail':'pass';
    }catch(error){statusNode.textContent=String(error);report.error=String(error);}
    showReport();document.querySelectorAll('button').forEach(button=>button.disabled=false);
}
document.getElementById('run').onclick=runCatalogue;
document.getElementById('regressions').onclick=runRegressions;

if(new URL(location.href).searchParams.has('autorun')||new URL(location.href).searchParams.has('fresh')) runCatalogue();
