'use strict';
// Startup diagnostics for the stock 25.107 ARM client. This is not yet a
// plaintext protocol patch: encryption remains active.
const log = new NativeFunction(Process.getModuleByName('liblog.so').getExportByName('__android_log_write'), 'int', ['int','pointer','pointer']);
const tag = Memory.allocUtf8String('Terra25');
function note(s) { log(4, tag, Memory.allocUtf8String(s)); }
const libc = Process.getModuleByName('libc.so');
const inetAddr = new NativeFunction(libc.getExportByName('inet_addr'), 'uint32', ['pointer']);
Interceptor.attach(libc.getExportByName('connect'), {
  onEnter(args) {
    const addr = args[1];
    if (addr.isNull() || addr.readU16() !== 2) return;
    const port = (addr.add(2).readU8() << 8) | addr.add(3).readU8();
    if (port !== 9339) return;
    addr.add(4).writeU32(inetAddr(Memory.allocUtf8String('127.0.0.1')));
    note('redirected port 9339 to 127.0.0.1; stock encryption still active');
  }
});
note('diagnostic gadget loaded');
