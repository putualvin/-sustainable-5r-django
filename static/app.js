'use strict';
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
const menu = document.getElementById('menu-toggle');
menu?.addEventListener('click', () => {const open=document.getElementById('navigation').classList.toggle('open');menu.setAttribute('aria-expanded', String(open));});
function connection(){const node=document.getElementById('connection');if(node){node.classList.toggle('disconnected',!navigator.onLine);node.replaceChildren(Object.assign(document.createElement('i'),{}),document.createTextNode(navigator.onLine?'Online':'Offline'));}document.getElementById('offline-banner')?.toggleAttribute('hidden',navigator.onLine);}
window.addEventListener('online',connection);window.addEventListener('offline',connection);connection();
document.querySelectorAll('[data-audit-tab]').forEach(button=>button.addEventListener('click',()=>{document.querySelector('.audit-workspace').classList.toggle('show-previous',button.dataset.auditTab==='previous');document.querySelectorAll('[data-audit-tab]').forEach(b=>b.classList.toggle('selected',b===button));}));
const dialog=document.getElementById('photo-dialog');
document.querySelectorAll('[data-photo]').forEach(button=>button.addEventListener('click',()=>{document.getElementById('photo-large').src=button.dataset.photo;dialog.showModal();}));
document.getElementById('close-photo')?.addEventListener('click',()=>dialog.close());
dialog?.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
document.querySelectorAll('input[type=file]').forEach(input=>input.addEventListener('change',()=>{const preview=input.closest('form').querySelector('.upload-preview');if(preview && input.files[0]){if(preview.dataset.url)URL.revokeObjectURL(preview.dataset.url);const url=URL.createObjectURL(input.files[0]);preview.src=url;preview.dataset.url=url;preview.hidden=false;}}));
document.querySelectorAll('form[data-confirm]').forEach(form=>form.addEventListener('submit',event=>{if(!window.confirm(form.dataset.confirm))event.preventDefault();}));
document.getElementById('download-audit')?.addEventListener('click',async event=>{
  const button=event.currentTarget, label=document.getElementById('offline-download-status');button.disabled=true;
  try{
    const response=await fetch(`/api/audit/${button.dataset.audit}/`,{credentials:'same-origin'});
    if(!response.ok)throw Error('Audit tidak dapat diunduh. Pastikan login dan penugasan masih aktif.');
    const data=await response.json();
    label.textContent='Menyiapkan foto dan pertanyaan untuk offline…';
    for(const review of data.reviews){const photo=await fetch(review.photo,{credentials:'same-origin'});if(!photo.ok)throw Error('Foto tidak berhasil diunduh.');review.photoBlob=await photo.blob();}
    await new Promise((resolve,reject)=>{const open=indexedDB.open('5r-offline',1);open.onupgradeneeded=()=>{open.result.createObjectStore('audits',{keyPath:'key'});open.result.createObjectStore('queue',{keyPath:'id'});};open.onerror=()=>reject(open.error);open.onsuccess=()=>{const db=open.result, tx=db.transaction('audits','readwrite');tx.objectStore('audits').put({...data,key:`${data.user}:${data.id}`});tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};});
    if(navigator.storage?.persist)await navigator.storage.persist();
    label.replaceChildren(document.createTextNode('Audit dan foto tersedia di perangkat. '));const link=document.createElement('a');link.href=`/offline/?audit=${data.id}&user=${data.user}`;link.textContent='Buka ruang audit offline →';label.append(link);
  }catch(error){label.textContent='Gagal menyiapkan offline. '+error.message;}finally{button.disabled=false;}
});
document.querySelector('.logout-form')?.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget;
  const open=indexedDB.open('5r-offline',1);
  open.onupgradeneeded=()=>{open.result.createObjectStore('audits',{keyPath:'key'});open.result.createObjectStore('queue',{keyPath:'id'});};
  open.onerror=()=>{if(confirm('Keluar? Data offline lokal akan dibersihkan.'))form.submit();};
  open.onsuccess=()=>{const db=open.result, tx=db.transaction('queue'), req=tx.objectStore('queue').count();req.onsuccess=()=>{db.close();if(req.result && !confirm('Ada draf offline belum tersinkronisasi. Keluar akan menghapus draf di perangkat ini. Tetap keluar?'))return;const remove=indexedDB.deleteDatabase('5r-offline');remove.onsuccess=()=>form.submit();remove.onerror=()=>alert('Tutup tab offline lain lalu coba keluar kembali.');remove.onblocked=()=>alert('Tutup tab offline lain sebelum keluar agar data lokal bisa dibersihkan.');};};
});
