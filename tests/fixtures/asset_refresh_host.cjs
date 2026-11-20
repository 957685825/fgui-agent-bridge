// 执行真实编译插件，验证外部新增/修改/删除与刷新等待边界。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
let files = { '/probe/assets/package/package.xml': [10, 1] };
let queued = false, processing = false, dirty = false, failScan = false, refreshes = 0;
let stageResets = 0, arrowResets = 0;
const listeners = {};
const array = values => ({ Length: values.length, GetValue(i) { return values[i]; } });
const time = { unscaledTime: 0 };
const mouse = [false, false, false];
const input = { anyKey: false, GetMouseButton(i) { return mouse[i]; } };
const app = {
    project: null, groot: { hasModalWindow: false, modalWaiting: false },
    docView: { HasUnsavedDocuments() { return dirty; } },
    consoleView: { Log() {}, LogError() {} },
    RefreshProject() { refreshes++; },
};
const events = ['onUpdate', 'onProjectOpened', 'onProjectClosed'];
for (let i = 0; i < events.length; i++) {
    const name = events[i];
    app['add_' + name] = fn => { listeners[name] = fn; };
    app['remove_' + name] = () => { delete listeners[name]; };
}
const application = { runInBackground: false, isFocused: true, add_focusChanged() {}, remove_focusChanged() {} };
const context = vm.createContext({ exports: {}, require() { return {}; }, CS: {
    UnityEngine: { Time: time, Input: input, Application: application },
    FairyEditor: { App: app, ArrowKeyHelper: { Reset() { arrowResets++; } } },
    FairyGUI: { Stage: { inst: { ResetInputState() { stageResets++; } } } },
    System: { IO: {
        SearchOption: { AllDirectories: 1 }, Path: { GetFileName: path.basename },
        Directory: { GetFiles(folder) {
            if (folder === 'requests') return array(queued ? ['request.json'] : []);
            if (folder === 'processing') return array(processing ? ['request.json'] : []);
            if (failScan) throw new Error('file replaced');
            return array(Object.keys(files));
        } },
        FileInfo: function(file) { this.Length = files[file][0]; },
        File: { GetLastWriteTimeUtc(file) { return { Ticks: files[file][1] }; }, AppendAllText() {} }
    } }
} });
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
let nestedStale = false;
let reloads = 0;
const doc = { content: { ValidateChildren(checkOnly) { assert.equal(checkOnly, true); return nestedStale; } },
    isModified: false, savedVersion: 1, packageItem: { version: 1 },
    DiscardChanges() { this.savedVersion = this.packageItem.version; nestedStale = false; reloads++; } };
app.activeDoc = doc;
app.project = { assetsPath: '/probe/assets', opened: true };
vm.runInContext('requestFolder="requests"; processingFolder="processing";', context);
function tick() { time.unscaledTime += 2; context.refreshExternalAssetsWhenIdle(); }
function changed() { files['/probe/assets/package/package.xml'][1]++; tick(); }
function recoverAfter(seconds) { time.unscaledTime += seconds; context.recoverInputWhenIdle(); }
function assertResets(expected) { assert.equal(stageResets, expected); assert.equal(arrowResets, expected); }
tick(); tick(); assert.equal(refreshes, 0);
recoverAfter(0); recoverAfter(0.51); assertResets(0);
files['/probe/assets/new/package.xml'] = [20, 1];
tick(); assert.equal(refreshes, 0, 'wait for stable disk state');
files['/probe/assets/new/package.xml'][1]++;
tick(); assert.equal(refreshes, 0); tick(); assert.equal(refreshes, 1);
// 原生刷新结束后，即使没有 Bridge 请求或窗口焦点事件，也应恢复输入。
// 恢复仍须等待真实鼠标操作松开并连续空闲半秒。
mouse[0] = true; recoverAfter(0); recoverAfter(0.51); assertResets(0);
mouse[0] = false; recoverAfter(0); recoverAfter(0.49); assertResets(0);
recoverAfter(0.02); assertResets(1);
// 模拟原生异步版本更新：下一轮才刷新当前画布，无关版本不重载。
doc.packageItem.version = 2; tick(); assert.equal(reloads, 1);
// 异步加载后的画布重载是另一次原生操作，也需要等待键盘空闲后恢复。
input.anyKey = true; recoverAfter(0); recoverAfter(0.51); assertResets(1);
input.anyKey = false; recoverAfter(0); recoverAfter(0.51); assertResets(2);
tick(); assert.equal(reloads, 1);
recoverAfter(0); recoverAfter(0.51); assertResets(2);
nestedStale = true; tick(); assert.equal(reloads, 2, 'nested resource update');
app.activeDoc = null; doc.packageItem.version = 3; tick(); assert.equal(reloads, 2);
app.activeDoc = doc; tick(); assert.equal(reloads, 3, 'reload when user activates stale tab');
changed(); dirty = true; tick(); tick(); assert.equal(refreshes, 1);
dirty = false; tick(); assert.equal(refreshes, 2, 'resume after user saves/discards');
const blockers = [
    value => { queued = value; }, value => { processing = value; },
    value => { app.groot.hasModalWindow = value; }, value => { app.groot.modalWaiting = value; },
    value => vm.runInContext('publishInProgress=' + value, context),
    value => { input.anyKey = value; },
    value => { mouse[0] = value; }, value => { mouse[1] = value; }, value => { mouse[2] = value; }
];
for (let i = 0; i < blockers.length; i++) {
    const before = refreshes;
    changed(); blockers[i](true); tick(); tick(); assert.equal(refreshes, before);
    blockers[i](false); tick(); tick(); assert.equal(refreshes, before + 1);
}
const before = refreshes;
files['/probe/assets/.DS_Store'] = [10, 1]; files['/probe/assets/edit.xml.tmp'] = [10, 1];
tick(); tick(); assert.equal(refreshes, before, 'ignore common temporary files');
files = {}; tick(); assert.equal(refreshes, before); tick(); assert.equal(refreshes, before + 1);
files['/probe/assets/package/package.xml'] = [10, 5];
failScan = true; tick(); assert.equal(refreshes, before + 1);
failScan = false; tick(); tick(); assert.equal(refreshes, before + 2);
context.resetAssetRefresh(); tick(); tick(); assert.equal(refreshes, before + 2, 'reset baseline on project switch');
context.exports.onDestroy(); assert.deepEqual(Object.keys(listeners), []);
console.log('asset refresh host checks passed');
