'use strict';
const libc=Process.getModuleByName('libc.so');
const cfn=(n,r,a)=>new NativeFunction(libc.getExportByName(n),r,a);
const sendraw=cfn('send','int',['int','pointer','uint','int']);
const recvraw=new SystemFunction(libc.getExportByName('recv'),'int',['int','pointer','uint','int']);
const alloc=cfn('malloc','pointer',['uint']);const free=cfn('free','void',['pointer']);
const lock=cfn('pthread_mutex_lock','int',['pointer']);const unlock=cfn('pthread_mutex_unlock','int',['pointer']);
let fd=-1,g=null,messaging=null,rx=[],initialized=false;
const credentialPath='/data/user/0/com.terra.brawl25/files/terra-account.json';
function readCredentials(){try{return JSON.parse(File.readAllText(credentialPath));}catch(e){return {id:0,token:null};}}
function storeCredentials(body){try{let v=new DataView(new Uint8Array(body).buffer),id=v.getInt32(4,false),n=v.getInt32(16,false);if(id<=0||n<=0||n>256||20+n>body.length)return;let token=String.fromCharCode(...body.slice(20,20+n));let f=new File(credentialPath,'w');f.write(JSON.stringify({id:id,token:token}));f.flush();f.close();send('saved local account '+id);}catch(e){send('credential save failed '+e);}}
function i32(n){return [(n>>>24)&255,(n>>>16)&255,(n>>>8)&255,n&255];}
function str(s){if(s===null)return [255,255,255,255];let b=Array.from(unescape(encodeURIComponent(s)),c=>c.charCodeAt(0));return [...i32(b.length),...b];}
function packet(t,b,ver=0){return [(t>>8)&255,t&255,(b.length>>16)&255,(b.length>>8)&255,b.length&255,(ver>>8)&255,ver&255,...b];}
function transmit(bytes){let p=Memory.alloc(bytes.length);p.writeByteArray(bytes);let r=sendraw(fd,p,bytes.length,0);send('sent bytes '+r);}
function login(){let credentials=readCredentials();let b=[...i32(0),...i32(credentials.id),...str(credentials.token),...i32(25),...i32(0),...i32(107),...str('d455da1d1c10bd83795f76fd0319a4a32a34ef86'),...i32(0),...str(''),...str(''),...str('Android')];transmit(packet(10101,b));let temp=alloc(4096);let timeout=Memory.alloc(8);timeout.writeS32(5);timeout.add(4).writeS32(0);cfn('setsockopt','int',['int','int','int','pointer','uint'])(fd,1,20,timeout,8);try{let r=recvraw(fd,temp,4096,0);send('blocking recv '+r.value+' errno '+r.errno);timeout.writeS32(0);cfn('setsockopt','int',['int','int','int','pointer','uint'])(fd,1,20,timeout,8);if(r.value>0){rx.push(...new Uint8Array(temp.readByteArray(r.value)));pump();}}finally{free(temp);}}
function deliver(type,version,body){
 send('DELIVER START '+type+' '+body.length);
 if(type===20104)storeCredentials(body);
 let factory=messaging.add(0x34).readPointer();let create=new NativeFunction(g.base.add(0x89484),'pointer',['pointer','int']);let m=create(factory,type);if(m.isNull()){send('unknown message '+type);return;}
 m.add(4).writeS32(version);let stream=m.add(8);stream.add(0x14).writeS32(body.length);if(body.length){let p=alloc(body.length);p.writeByteArray(body);stream.add(0x1c).writePointer(p);}
 let decode=new NativeFunction(m.readPointer().add(0xc).readPointer(),'void',['pointer']);decode(m);
 if(type===20104) messaging.add(0xd4).writeS32(5);
 let q=messaging.add(0x3c);lock(q.sub(4));let tail=q.add(0x10).readS32();let cap=q.add(4).readS32();q.readPointer().add(tail*4).writePointer(m);q.add(0x10).writeS32((tail+1)%cap);q.add(8).writeS32(q.add(8).readS32()+1);unlock(q.sub(4));send('delivered '+type+' length '+body.length);
}
function pump(){let p=alloc(4096);try{for(;;){let r=recvraw(fd,p,4096,0x40);if(r.value<=0)break;rx.push(...new Uint8Array(p.readByteArray(r.value)));}while(rx.length>=7){let t=rx[0]*256+rx[1],n=rx[2]*65536+rx[3]*256+rx[4],v=rx[5]*256+rx[6];if(n>2097152)throw Error('invalid size');if(rx.length<7+n)break;let body=rx.slice(7,7+n);rx=rx.slice(7+n);send('PACKET '+t+' len '+n);deliver(t,v,body);}}finally{free(p);}}
Interceptor.attach(libc.getExportByName('connect'),{onEnter(a){let x=a[1];if(x.isNull()||x.readU16()!==2)return;let p=(x.add(2).readU8()<<8)|x.add(3).readU8();if(p!==9339)return;g=Process.getModuleByName('libg.so');fd=a[0].toInt32();x.add(4).writeByteArray([127,0,0,1]);x.add(2).writeByteArray([0x24,0x7b]);send('redirected '+fd);
 if(initialized)return;initialized=true;
 Interceptor.attach(g.base.add(0x16500c), {onEnter(a){
   const mode=a[3].toInt32();
   send('battle launch mode '+mode);
   if(mode===1){transmit(packet(14103,[]));a[3]=ptr(3);send('starting local bot simulation');}
 }});send('battle hook armed');
 Interceptor.replace(g.base.add(0x46c598),new NativeCallback(function(self,socket,msg){try{let typ=new NativeFunction(msg.readPointer().add(0x14).readPointer(),'int',['pointer'])(msg);send('native outgoing '+typ);messaging=self;if(typ===10100)login();else if(typ===10108)transmit(packet(10108,[]));else if(typ===10212||typ===14600||typ===14103||typ===14101||typ===14109||typ===14110||typ===14106||typ===14102){let encode=new NativeFunction(msg.readPointer().add(8).readPointer(),'void',['pointer']);encode(msg);let stream=msg.add(8),n=stream.add(0x10).readS32();if(n<0||n>65536)throw Error('invalid encoded length');let bytes=n?Array.from(new Uint8Array(stream.add(0x1c).readPointer().readByteArray(n))):[];transmit(packet(typ,bytes,msg.add(4).readU16()));}}catch(e){send('send error '+e);}return 1;},'int',['pointer','pointer','pointer']));
}});
Interceptor.attach(libc.getExportByName('select'),{onEnter(a){this.set=null;if(fd<0||!messaging||a[1].isNull())return;let w=a[1].add((fd>>>5)*4),mask=(1<<(fd&31))>>>0;if((w.readU32()&mask)!==0){this.set=w;this.mask=mask;}},onLeave(result){if(!this.set||result.toInt32()<=0||(this.set.readU32()&this.mask)===0)return;try{pump();this.set.writeU32((this.set.readU32()&~this.mask)>>>0);result.replace(Math.max(0,result.toInt32()-1));}catch(e){send('receive error '+e);}}});
setInterval(function(){if(fd>=0 && messaging){try{pump();}catch(e){send('timer receive error '+e);}}},20);
send('ready');
