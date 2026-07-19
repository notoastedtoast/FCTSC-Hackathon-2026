
const CACHE_NAME="scamcheck-shell-v9";
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

  const cacheKey=url.pathname;
  const updateCache=async()=>{
    const response=await fetch(request);
    if(!response.ok)return response;
    const cache=await caches.open(CACHE_NAME);
    await cache.put(cacheKey,response.clone());
    return response;
  };

  if(cacheKey!=="/"){
    const refresh=updateCache();
    event.waitUntil(refresh.then(()=>undefined).catch(()=>undefined));
    event.respondWith((async()=>{
      const cached=await caches.match(cacheKey);
      if(cached)return cached;
      try{
        return await refresh;
      }catch(error){
        return Response.error();
      }
    })());
    return;
  }

  event.respondWith((async()=>{
    const cached=await caches.match(cacheKey);
    try{
      const response=await updateCache();
      return response.ok||!cached?response:cached;
    }catch(error){
      return cached||Response.error();
    }
  })());
});
