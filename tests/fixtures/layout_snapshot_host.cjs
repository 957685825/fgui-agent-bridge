// 执行实际编译插件，覆盖锚点/仿射坐标、视口裁切重建及失败后的状态恢复。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let captures = 0, destroyed = 0, updates = 0, painting = 2, prepared = false, begins = 0, ends = 0;
let invalidFormat = false, invalidLength = false, encodeFails = false;
let captureFails = false, updateFails = false, missingTexture = false, wrongSize = false;
const nativePixels = Buffer.alloc(100 * 80 * 4);
Buffer.from([0, 0, 255, 255, 255, 0, 0, 128]).copy(nativePixels);
const texture = {
    get width() { return wrongSize ? 1 : 100; }, height: 80,
    get format() { return invalidFormat ? 99 : 4; },
    GetRawTextureData() { return { Length: nativePixels.length - (invalidLength ? 1 : 0), buffer: nativePixels }; }
};
const app = { project: null, consoleView: { Log() {}, LogError() {} },
    pluginManager: { allPlugins: { Count: 0 } },
    add_onUpdate() {}, add_onProjectOpened() {}, add_onProjectClosed() {}
};
const context = vm.createContext({ exports: {}, require() { return {}; }, CS: {
    System: { IO: {}, Convert: { ToBase64String(value) {
        if (encodeFails) throw new Error('encoding failed');
        return value.buffer.toString('base64');
    } } },
    UnityEngine: { Application: { runInBackground: false, add_focusChanged() {} },
        Vector2: class { constructor(x, y) { this.x = x; this.y = y; } },
        TextureFormat: { RGBA32: 4 }, Object: { Destroy(value) { assert.equal(value, texture); destroyed++; } }
    },
    FairyGUI: { UpdateContext: class {
        Begin() { begins++; this.clipped = false; this.rectMaskDepth = 0; }
        End() { ends++; }
    }, Stage: { inst: { ForceUpdate() { updates++; prepared = false; } } } },
    FairyEditor: { App: app, FObjectType: { MOVIECLIP: 'movieclip' } }
} });
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
// 矩阵直接给定相对根画布的预期坐标；宿主视口再叠加缩放和平移。
let zoom = 2, panX = 100, panY = 60;
function node(id, matrix, width, height) {
    return { id, name: id, objectType: 'component', x: matrix[4], y: matrix[5], width, height,
        alpha: 1, visible: true, internalVisible: true, hideByEditor: false,
        LocalToGlobal() { throw new Error('FObject anchor coordinate API must not be used'); },
        displayObject: {
            LocalToGlobal(point) { return { x: (matrix[0] * point.x + matrix[2] * point.y + matrix[4]) * zoom + panX,
                y: (matrix[1] * point.x + matrix[3] * point.y + matrix[5]) * zoom + panY }; },
            GlobalToLocal(point) {
                const x = (point.x - panX) / zoom - matrix[4], y = (point.y - panY) / zoom - matrix[5];
                const det = matrix[0] * matrix[3] - matrix[1] * matrix[2];
                return { x: (matrix[3] * x - matrix[2] * y) / det, y: (-matrix[1] * x + matrix[0] * y) / det };
            },
            TransformPoint(point, target) { return target.GlobalToLocal(this.LocalToGlobal(point)); }
        }
    };
}
const root = node('root', [1, 0, 0, 1, 0, 0], 100, 80);
root.GlobalToLocal = () => { throw new Error('FObject anchor coordinate API must not be used'); };
const nested = node('nested', [0, 1, 1, 0, 50, 20], 20, 10);
const label = node('label', [0, 1, 1, 0, 54, 23], 4, 2);
nested.parent = root; label.parent = nested;
label.pivotX = 0.5; label.pivotY = 0.5; label.anchor = true;
label.font = 'Custom'; label.fontSize = 24; label.text = '+80'; label.autoSize = 'shrink';
label.numChildren = 0; label.GetChildAt = () => { throw new Error('unexpected'); };
nested.numChildren = 1; nested.GetChildAt = () => label;
root.numChildren = 1; root.GetChildAt = () => nested;
root.controllers = { Count: 1, get_Item() { return { name: 'state', selectedIndex: 1, selectedPage: 'premium' }; } };
root.designImage = 'ui://reference'; root.designImageOffsetX = 7; root.designImageOffsetY = -3;
root.displayObject.Update = context => {
    updates++;
    assert.equal(context.clipped, false);
    assert.equal(context.rectMaskDepth, 0, 'internal masks must not inherit editor viewport clipping depth');
    if (updateFails) { updateFails = false; throw new Error('update failed'); }
    prepared = Boolean(painting & 1048576);
};
root.displayObject.EnterPaintingMode = (id, margin, scale) => {
    assert.equal(margin, null); assert.equal(scale, 1); assert.equal(painting & id, 0); painting |= id;
};
root.displayObject.LeavePaintingMode = id => { assert.ok(painting & id); painting &= ~id; };
root.displayObject.GetScreenShot = (margin, scale) => {
    assert.equal(margin, null); assert.equal(scale, 1);
    assert.ok(prepared, 'must refresh clipping materials before capturing');
    assert.ok(painting & 1048576, 'keep own painting request while native capture toggles its request');
    captures++;
    if (captureFails) throw new Error('capture failed');
    return missingTexture ? null : texture;
};
const doc = { docURL: 'ui://test', content: root, isModified: true, savedVersion: 8, GetSelection() { return { Count: 1 }; } };
app.activeDoc = doc;
const read = params => context.handleCommand({ action: 'get_layout_snapshot', params });
const plain = value => JSON.parse(JSON.stringify(value));
// 普通根、居中锚点根及不同画布缩放/平移，子节点还有旋转和镜像。
for (let i = 0; i < 3; i++) {
    root.anchor = i !== 0; root.pivotX = i / 2; root.pivotY = i / 2;
    zoom = [0.5, 1, 2][i]; panX = 100 - 500 * i; panY = 60 + 200 * i;
    const snapshot = read({ includeImage: false });
    assert.deepEqual(plain(snapshot.tree.rootBounds), { x: 0, y: 0, width: 100, height: 80 });
    assert.equal(snapshot.reference.offsetX, 7); assert.equal(snapshot.reference.offsetY, -3);
    assert.equal(snapshot.tree.controllers[0].selectedPage, 'premium');
    const actual = snapshot.tree.children[0].children[0];
    assert.deepEqual(plain(actual.rootBounds), { x: 54, y: 23, width: 2, height: 4 });
    assert.deepEqual(plain(actual.rootCorners), [{ x: 54, y: 23 }, { x: 54, y: 27 }, { x: 56, y: 27 }, { x: 56, y: 23 }]);
    assert.equal(actual.parentId, 'nested'); assert.equal(actual.textStyle.fontSize, 24); assert.equal(actual.anchor, true);
}
assert.equal(captures, 0); assert.equal(updates, 0);
const shallow = read({ maxDepth: 1, includeImage: false });
assert.equal(shallow.tree.children[0].childrenTruncated, true);
assert.equal(shallow.tree.children[0].children, undefined);
assert.throws(() => read({ maxDepth: 1.5 }), /maxDepth/);
assert.throws(() => read({ maxDepth: 65 }), /maxDepth/);
assert.throws(() => read({ includeImage: 'false' }), /includeImage/);
assert.equal(read({}).capture.rgbaBase64, nativePixels.toString('base64'));
assert.equal(captures, 1); assert.equal(destroyed, 1); assert.equal(updates, 2);
function restored() {
    assert.equal(painting, 2, 'preserve existing painting request');
    assert.equal(prepared, false, 'restore viewport clipping');
    assert.equal(begins, ends, 'end isolated context even when subtree update fails');
    assert.equal(doc.isModified, true); assert.equal(doc.savedVersion, 8); assert.equal(app.activeDoc, doc);
}
restored();
const failureCases = [
    [() => { invalidFormat = true; }, () => { invalidFormat = false; }, /RGBA32/, true],
    [() => { invalidLength = true; }, () => { invalidLength = false; }, /像素长度/, true],
    [() => { encodeFails = true; }, () => { encodeFails = false; }, /encoding failed/, true],
    [() => { wrongSize = true; }, () => { wrongSize = false; }, /尺寸与根画布不一致/, true],
    [() => { missingTexture = true; }, () => { missingTexture = false; }, /未返回/, false],
    [() => { captureFails = true; }, () => { captureFails = false; }, /capture failed/, false],
    [() => { updateFails = true; }, () => {}, /update failed/, false]
];
for (let i = 0; i < failureCases.length; i++) {
    const test = failureCases[i], before = destroyed;
    test[0](); assert.throws(() => read({}), test[2]); test[1]();
    assert.equal(destroyed, before + (test[3] ? 1 : 0)); restored();
}
root.width = 5000;
const before = captures;
assert.throws(() => read({}), /4096/); assert.equal(captures, before);
assert.equal(read({ includeImage: false }).canvas.width, 5000);
restored();
console.log('layout snapshot host checks passed');
