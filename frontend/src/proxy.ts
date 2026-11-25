import { NextResponse, type NextRequest } from "next/server";

/**
 * Optimistic auth gate: app routes require the session cookie set by the API. The backend remains
 * the source of truth - it validates the JWT on every request (an expired token yields 401 and the
 * client redirects to /login).
 */
const COOKIE = "airsense_token";

export function proxy(request: NextRequest) {
  const has = request.cookies.has(COOKIE);
  const { pathname, search } = request.nextUrl;
  if (!has) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/analytics/:path*", "/forecast/:path*", "/models/:path*", "/map/:path*",
    "/alerts/:path*", "/settings/:path*"],
};
