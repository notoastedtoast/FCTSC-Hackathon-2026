const CACHE_NAME="scamcheck-shell-v7";
const APP_SHELL=["/","/styles.css","/offline-analyzer.js","/app.js","/scamcheck-logo.png"];

self.addEventListener("install",event=>{
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache=>cache.addAll(APP_SHELL))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener("activate",event=>{
  event.waitUntil(
    caches.keys()
      .then(names=>Promise.all(
        names
          .filter(name=>name.startsWith("scamcheck-shell-")&&name!==CACHE_NAME)
          .map(name=>caches.delete(name))
      ))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET")return;

  const url=new URL(request.url);
  if(url.origin!==self.location.origin||!APP_SHELL.includes(url.pathname))return;

  if(url.pathname==="/"){
    event.respondWith(
      fetch(request)
        .then(response=>{
          if(response.ok){
            const copy=response.clone();
            void caches.open(CACHE_NAME).then(cache=>cache.put("/",copy));
          }
          return response;
        })
        .catch(()=>caches.match("/"))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(cached=>cached||fetch(request))
  );
});
