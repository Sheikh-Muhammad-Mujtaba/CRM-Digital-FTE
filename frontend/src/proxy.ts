import { NextRequest, NextResponse } from "next/server";

import { ADMIN_GATE_COOKIE } from "@/lib/admin-auth";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/admin/login" || pathname.startsWith("/admin/login/")) {
    return NextResponse.next();
  }

  const hasAdminGate = request.cookies.get(ADMIN_GATE_COOKIE)?.value === "1";
  if (!hasAdminGate) {
    const loginUrl = new URL("/admin/login", request.url);
    loginUrl.searchParams.set("reason", "expired");
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
