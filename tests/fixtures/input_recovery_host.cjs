// 用宿主替身执行实际编译后的插件，验证恢复不会打断真实按键或拖动。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const listeners = {};
const mouse = [false, false, false];
let stageResets = 0;
let arrowResets = 0;
const application = {
    runInBackground: false, isFocused: true,
    add_focusChanged(fn) { listeners.focus = fn; },
    remove_focusChanged(fn) { assert.equal(listeners.focus, fn); delete listeners.focus; }
};
const input = { anyKey: false, GetMouseButton(i) { return mouse[i]; } };
const time = { unscaledTime: 0 };
const app = { project: null,
    consoleView: { Log() {}, LogError() {} },
    pluginManager: { allPlugins: { Count: 0 } }
};
const events = ['onUpdate', 'onProjectOpened', 'onProjectClosed'];
for (let i = 0; i < events.length; i++) {
    const name = events[i];
    app['add_' + name] = fn => { listeners[name] = fn; };
    app['remove_' + name] = fn => { assert.equal(listeners[name], fn); delete listeners[name]; };
}
const file = { Exists() { return false; }, WriteAllText() {}, Move() {}, Delete() {},
    ReadAllText() { return JSON.stringify({ id: 'test', action: 'get_tree' }); } };
const context = vm.createContext({ exports: {}, require() { return {}; }, CS: {
    System: { IO: { File: file, Directory: {}, Path: {
        Combine(...parts) { return parts.join('/'); },
        GetFileName: path.basename,
        GetFileNameWithoutExtension(name) { return path.basename(name, '.json'); }
    } } },
    UnityEngine: { Application: application, Input: input, Time: time },
    FairyEditor: { App: app, ArrowKeyHelper: { Reset() { arrowResets++; } } },
    FairyGUI: { Stage: { inst: { ResetInputState() { stageResets++; } } } }
} });
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
// 宿主在入口执行后读取导出的生命周期函数；加载时插件列表可能还没有自身。
assert.equal(typeof context.exports.onDestroy, 'function', 'must export the host lifecycle hook');
function tick(at) { time.unscaledTime = at; listeners.onUpdate(); }
function resets(expected) { assert.equal(stageResets, expected); assert.equal(arrowResets, expected); }
function success() { context.completeRequestSuccess('claimed', 'test', 'get_tree', {}); }
function focus(focused) {
    application.isFocused = focused;
    if (listeners.focus) listeners.focus(focused);
}

async function main() {
    // 普通更新/心跳不触发恢复；请求后仍按着 Shift 时必须等待。
    tick(0); tick(10); resets(0);
    success(); input.anyKey = true; tick(11); tick(12); resets(0);
    input.anyKey = false; tick(13); tick(13.49); resets(0);
    tick(13.51); resets(1); tick(20); resets(1);

    // 三种鼠标按键都阻止恢复，松开后重新计算连续空闲时间。
    for (let i = 0; i < mouse.length; i++) {
        success(); mouse[i] = true; tick(30 + i * 4); tick(31 + i * 4); resets(1 + i);
        mouse[i] = false; tick(32 + i * 4); tick(32.51 + i * 4); resets(2 + i);
    }
    success(); tick(50); input.anyKey = true; tick(50.3);
    input.anyKey = false; tick(50.4); tick(50.8); resets(4); tick(50.91); resets(5);

    // 后台不重置；回到前台后恢复一次。失败请求和异步完成也覆盖。
    success(); application.isFocused = false; tick(60); tick(61); resets(5);
    application.isFocused = true; listeners.focus(true); tick(62); tick(62.51); resets(6);
    context.completeRequestError('claimed', 'test', 'get_tree', new Error('expected'));
    tick(70); tick(70.51); resets(7);
    context.handleCommand = () => Promise.resolve({});
    context.processRequestFile('test.json');
    await Promise.resolve(); await Promise.resolve();
    tick(80); tick(80.51); resets(8);
    context.handleCommand = () => Promise.reject(new Error('expected async'));
    context.processRequestFile('test.json');
    await Promise.resolve(); await Promise.resolve();
    tick(90); tick(90.51); resets(9);

    // 卸载撤销监听并恢复原后台设置，不留下等待中的重置。
    success(); context.exports.onDestroy();
    assert.equal(application.runInBackground, false);
    assert.deepEqual(Object.keys(listeners), []);
    assert.equal(vm.runInContext('inputRecoveryPending', context), false);
    // 旧环境卸载后再切焦点不会触发任何回调；第二次加载也能独立注册和释放。
    focus(false); focus(true); resets(9);
    const reloaded = vm.createContext({ ...context, exports: {} });
    vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), reloaded);
    assert.equal(Object.keys(listeners).length, 4);
    focus(false); focus(true);
    tick(100); tick(100.51); resets(10);
    // 即使宿主菜单清理失败，事件也必须已经解绑并恢复后台设置。
    vm.runInContext('toolMenu = { RemoveItem() { throw new Error("menu disposed"); } }', reloaded);
    assert.throws(() => reloaded.exports.onDestroy(), /menu disposed/);
    assert.deepEqual(Object.keys(listeners), []);
    assert.equal(application.runInBackground, false);
    focus(false); focus(true); resets(10);
    console.log('input recovery host checks passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
