export async function onRequest(context) {
  const url = new URL(context.request.url);

  if (url.hostname.toLowerCase() === "www.iceberglc.com") {
    url.hostname = "iceberglc.com";
    url.protocol = "https:";
    url.port = "";
    return Response.redirect(url.toString(), 301);
  }

  return context.next();
}
