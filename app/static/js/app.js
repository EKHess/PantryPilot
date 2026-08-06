document.querySelector('#menu')?.addEventListener('click',()=>document.querySelector('.sidebar').classList.toggle('open'));
document.querySelector('#settings-form')?.addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));const response=await fetch('/api/settings',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});document.querySelector('#live').textContent=response.ok?'Settings saved.':'Settings could not be saved.'});

