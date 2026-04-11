import type { Env } from "../types";
import { getNationalPctFailing, searchByZip } from "../db";
import { homePage, searchResultsPage } from "../templates/home";

export async function handleHome(request: Request, env: Env): Promise<Response> {
  const cached = await env.CACHE.get("page:home");
  if (cached)
    return new Response(cached, {
      headers: { "Content-Type": "text/html;charset=UTF-8" },
    });

  const pctFailing = await getNationalPctFailing(env);
  const html = homePage(pctFailing);
  await env.CACHE.put("page:home", html, { expirationTtl: 3600 });
  return new Response(html, {
    headers: { "Content-Type": "text/html;charset=UTF-8" },
  });
}

export async function handleSearch(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const zip = (url.searchParams.get("zip") ?? "").replace(/\D/g, "").slice(0, 5);
  if (zip.length !== 5) return Response.redirect("/", 302);

  const facilities = await searchByZip(env, zip);
  const html = searchResultsPage(zip, facilities);
  return new Response(html, {
    headers: { "Content-Type": "text/html;charset=UTF-8" },
  });
}
