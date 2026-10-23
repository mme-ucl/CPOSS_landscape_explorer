const { test } = require('node:test');
const assert = require('node:assert/strict');
const v = require('../assets/visualization.js');
const groups = require('../assets/spacegroups.js');
const property = values => ({ target: 'structure', values });
function dataset(values = [1, 2, 14, 230]) {
    return { meta: { name: 'Scientific adapter fixture' }, structures: values.map(() => ({size:1,names:['H'],x:[0],y:[0],z:[0]})), properties: {
        Density: property(values.map((_,i)=>1+i*.1)), 'Lattice Energy': property(values.map((_,i)=>-40+i*5)),
        'Space Group': property(values), 'Experimental Info': property(values.map(()=>'')),
    } };
}
function fakeApp() {
    return {
        async load(config, input) {
            this.input = input;
            let state = v.copy(input.settings);
            const options = {
                color:Object.fromEntries(Object.entries(state.map.color).map(([k,value])=>[k,{value}])),
                size:Object.fromEntries(Object.entries(state.map.size).map(([k,value])=>[k,{value}])),
                calculateColors(values) {
                    const finite=values.filter(Number.isFinite);
                    if(!finite.length)throw new Error('Native min/max: no finite values');
                    return values.map(x=>Math.min(...finite)===Math.max(...finite)?.5:this.color.mode.value==='log'?Math.log10(x):x);
                },
                calculateSizes: values => values.map(x=>x), valueToColor: value=>String(value),
            };
            const map = {
                _options:options,_computeLOD(){},_getNumericColors(){return options.calculateColors(input.properties[options.color.property.value].values).filter(x=>typeof x==='number');},
            };
            const callbacks=[];
            this.visualizer = {
                map, dataset:()=>v.copy(input), saveSettings:()=>v.copy(state), onSettingChange:fn=>callbacks.push(fn),
                applySettings(patch) {
                    state = v.merge(state,patch);
                    for(const part of ['color','size'])for(const[k,value]of Object.entries(state.map[part])){ options[part][k]??={};options[part][k].value=value; }
                    callbacks.forEach(fn=>fn());
                },
            };
            delete input.settings.map; // Native mutation must not affect source/preset.
        },
        fetchAndLoad(data){return this.load({},data);},loadStreaming(data){return this.load({loadStructure(){}},data);},
    };
}

test('one authoritative immutable global preset has the approved reference semantics',()=>{
    assert.equal(v.PRESET.map.x.property,'Density');assert.equal(v.PRESET.map.y.property,'Lattice Energy');
    assert.deepEqual(v.PRESET.map.color,{property:'Space Group Number',mode:'log',min:0,max:2.37,palette:'seismic'});
    assert.deepEqual(v.PRESET.map.size,{property:'Experimental Info',mode:'flip-linear',factor:55});
    assert.deepEqual(v.PRESET.structure,[{supercell:[3,3,3],unitCell:true}]);
    assert.ok(Object.isFrozen(v.PRESET.map.color));
});
test('validated symbol aliases cover all 230 international groups, settings and overbars',()=>{
    assert.deepEqual([...new Set(Object.values(groups.symbols))].sort((a,b)=>a-b),Array.from({length:230},(_,i)=>i+1));
    for(const [name,number]of Object.entries(groups.symbols))assert.equal(v.spaceGroup(name).number,number,name);
    for(const [name,number]of [['P 21/c',14],['P 1 21/c 1',14],['P2₁/c',14],['P 1̅',2],['I a -3 d',230],[' 14 ',14]])assert.equal(v.spaceGroup(name).number,number,name);
    for(const invalid of [0,231,-1,'P?','not a group',null,'nan','',2.5])assert.ok(Number.isNaN(v.spaceGroup(invalid).number));
});
test('numeric strings, textual symbols and row order resolve to physical SG numbers',()=>{
    const input=dataset(['14','P-1','Ia-3d','nan']);const before=v.copy(input),p=v.prepare(input);
    assert.deepEqual(p.dataset.properties[p.settings.map.color.property].values,[14,2,230,NaN]);
    assert.equal(p.diagnostics.spaceGroups.symbols,2);assert.equal(p.diagnostics.spaceGroups.unknown,1);
    assert.deepEqual(input,before);assert.equal(p.dataset.structures,input.structures);
});
test('category reordering cannot alter an international group number',()=>{
    const a=v.prepare(dataset(['P21/c','P-1','P1','Ia-3d']));const b=v.prepare(dataset(['Ia-3d','P1','P-1','P21/c']));
    assert.deepEqual(a.dataset.properties[a.settings.map.color.property].values,b.dataset.properties[b.settings.map.color.property].values.slice().reverse());
});
test('conflicting supplied numbers and symbols are unknown, never silently guessed',()=>{
    const input=dataset(['P21/c','P-1','P1','???']);input.properties['Space Group Number']=property([2,2,'nan',14]);
    const p=v.prepare(input);assert.deepEqual(p.dataset.properties[p.settings.map.color.property].values,[NaN,2,1,14]);
    assert.equal(p.diagnostics.spaceGroups.conflicts,1);
});
test('same-model axes prefer joint finite coverage with deterministic numeric model order',()=>{
    const input=dataset();input.properties={
        'Density (PBE+TS) 2 /gcm-3':property(['1','nan','3','4']),
        'Lattice Energy (PBE+TS) 2 /kJmol-1':property(['-40','null','-20','-10']),
        'Density 10 /gcm-3':property([1,2,3,4]),'Lattice Energy 10 /kJmol-1':property([-40,-30,-20,-10]),
        'Density 3 /gcm-3':property([1,2,3,4]),'Lattice Energy 3 /kJmol-1':property([-40,-30,-20,-10]),
    };
    let p=v.prepare(input);assert.equal(p.diagnostics.axes.model,'3');assert.equal(p.diagnostics.axes.plotted,4);
    input.properties['Density 3 /gcm-3'].values[0]=null;
    p=v.prepare(input);assert.equal(p.diagnostics.axes.model,'10');
    delete input.properties['Density 10 /gcm-3'];delete input.properties['Lattice Energy 10 /kJmol-1'];
    p=v.prepare(input);assert.equal(p.diagnostics.axes.model,'2');assert.equal(p.diagnostics.axes.plotted,3);
    assert.deepEqual(p.dataset.properties['Density (PBE+TS) 2 /gcm-3'].values,[1,NaN,3,4]);
});
test('axes recognize 2a, labels preceding/following models, units and never cross models',()=>{
    const input=dataset();input.properties={ 'Density 2a /gcm-3':property([1,2,3,4]),'Lattice Energy 2a /kJmol-1':property([-4,-3,-2,-1]) };
    assert.equal(v.prepare(input).diagnostics.axes.model,'2a');
    delete input.properties['Lattice Energy 2a /kJmol-1'];input.properties['Lattice Energy 3 /kJmol-1']=property([-4,-3,-2,-1]);
    const p=v.prepare(input);assert.equal(p.diagnostics.axes.model,null);assert.equal(p.diagnostics.axes.plotted,0);
    assert.ok(p.dataset.properties[p.settings.map.x.property].values.every(Number.isNaN));
});
test('different named unnumbered models do not form a false pair',()=>{
    const input=dataset();input.properties={'Density (model A) /gcm-3':property([1,2,3,4]),'Lattice Energy (model B) /kJmol-1':property([-4,-3,-2,-1])};
    assert.equal(v.prepare(input).diagnostics.axes.model,null);
});
test('all missing markers remain unknown, missing axes omit rows without alignment shifts',()=>{
    const input=dataset([NaN,null,'','N/A']);input.properties.Density.values=['1',null,'NaN','1.4'];
    const p=v.prepare(input);assert.deepEqual(p.dataset.properties[p.settings.map.color.property].values,[NaN,NaN,NaN,NaN]);
    assert.deepEqual(p.dataset.properties.Density.values,[1,NaN,NaN,1.4]);assert.equal(p.diagnostics.axes.missing,2);
    assert.equal(p.settings.map.color.property,'Space Group Number');assert.equal(p.settings.map.color.max,2.37);
    assert.match(v.describe(p).join(' '),/2 of 4 structures cannot be plotted/);
});
test('missing properties retain the same scientific style with grey SG and unavailable axes',()=>{
    const input=dataset();input.properties={Filename:property(['a','b','c','d'])};const p=v.prepare(input);
    assert.equal(p.settings.map.color.mode,'log');assert.equal(p.settings.map.size.mode,'flip-linear');
    assert.equal(p.diagnostics.spaceGroups.unknown,4);assert.equal(p.diagnostics.axes.plotted,0);
    assert.match(v.describe(p).join(' '),/scientific plot is empty/);
});
test('experimental descriptions retain labels and use deterministic presence scoring',()=>{
    const input=dataset();input.properties['Experimental Info']=property(['KNOWN FORM','','Another form','nan']);
    const p=v.prepare(input);assert.deepEqual(p.dataset.properties['Experimental Info'].values,input.properties['Experimental Info'].values);
    assert.deepEqual(p.dataset.properties[p.settings.map.size.property].values,[0,1,0,1]);
    assert.equal(p.diagnostics.experimentalInfo.policy,'annotation-presence');assert.equal(p.settings.map.size.factor,55);
    assert.equal(v.prepare(dataset()).dataset.properties['Experimental Info (size)'].values.every(x=>x===1),true);
});
test('numeric experimental values preserve measurements; missing sizes stay NaN',()=>{
    const input=dataset();input.properties['Experimental Info']=property(['0','2',null,'3']);const p=v.prepare(input);
    assert.equal(p.settings.map.size.property,'Experimental Info');assert.deepEqual(p.dataset.properties['Experimental Info'].values,[0,2,NaN,3]);
    assert.equal(p.diagnostics.experimentalInfo.policy,'numeric');
});
test('shared load paths enforce global style over embedded settings and preserve original exports',async()=>{
    for(const method of ['load','fetchAndLoad','loadStreaming']){
        const input=dataset(['14','nan','P-1',2]);input.settings={map:{x:{property:'Filename'},color:{mode:'linear',palette:'viridis'},size:{factor:99}},structure:[{supercell:[1,1,1]}]};
        const before=v.copy(input),app=fakeApp();v.install(app);
        if(method==='load')await app.load({},input);else await app[method](input);
        const settings=app.visualizer.saveSettings();assert.equal(settings.map.x.property,'Density');assert.equal(settings.map.color.mode,'log');assert.equal(settings.map.color.palette,'seismic');assert.equal(settings.map.size.factor,55);assert.deepEqual(settings.structure[0].supercell,[3,3,3]);
        assert.deepEqual(app.visualizer.dataset().properties,before.properties);assert.deepEqual(app.visualizer.dataset().settings,before.settings);assert.deepEqual(input,before);
        app.visualizer.applySettings({map:{color:{mode:'linear',palette:'viridis'},size:{factor:72}}});await Promise.resolve();
        assert.equal(app.visualizer.saveSettings().map.size.factor,72);assert.equal(app.visualizer.saveSettings().map.color.palette,'viridis');
    }
});
test('constant SG receives log10(number) exactly once, and unknowns stay grey',async()=>{
    const app=fakeApp();v.install(app);await app.load({},dataset([14,14,NaN,14]));
    const options=app.visualizer.map._options;
    assert.deepEqual(options.calculateColors([14,14,NaN,14]),[Math.log10(14),Math.log10(14),v.GREY,Math.log10(14)]);
    assert.deepEqual(options.calculateColors([NaN,NaN]),[v.GREY,v.GREY]);
    assert.equal(options.valueToColor(NaN,0,2.37),v.GREY);
});
test('all-unknown colour extent is only a native validation aid, never a replacement data row',async()=>{
    const app=fakeApp();v.install(app);await app.load({},dataset([NaN,NaN,NaN,NaN]));
    assert.deepEqual(app.visualizer.map._getNumericColors(),[0,2.37]);assert.equal(app.input.properties['Space Group Number'].values.length,4);
    assert.ok(app.input.properties['Space Group Number'].values.every(Number.isNaN));
});
test('nonstandard NaN parser preserves literal strings, escaped quotes and row alignment',()=>{
    const parsed=v.parseJSON('{"values":[NaN,"NaN","a\\\"NaN",null,"nan"]}');
    assert.deepEqual(parsed.values,[NaN,'NaN','a"NaN',null,'nan']);
});
test('unsupported native colour API fails visibly instead of loading a wrong-colour fallback',()=>{
    assert.throws(()=>v.patchNativeMap({},v.prepare(dataset())),/Unsupported Chemiscope/);
});
