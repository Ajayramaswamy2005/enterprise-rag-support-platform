import { type NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";
import { guestRegex, isDevelopmentEnvironment } from "./lib/constants";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/ping")) {
    return new Response("pong", { status: 200 });
  }

  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET,
    secureCookie: !isDevelopmentEnvironment,
  });

  const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

  const isAuthPage = ["/login", "/register"].includes(pathname);

  // Guests can't use the app (the chat layout requires a real account), so send
  // signed-out visitors straight to login instead of minting guest users.
  if (!token) {
    if (isAuthPage) {
      return NextResponse.next();
    }
    if (pathname.startsWith("/api/")) {
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }
    return NextResponse.redirect(new URL(`${base}/login`, request.url));
  }

  const isGuest = guestRegex.test(token?.email ?? "");

  if (!isGuest && isAuthPage) {
    return NextResponse.redirect(new URL(`${base}/`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/",
    "/chat/:id",
    "/api/:path*",
    "/login",
    "/register",

    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
