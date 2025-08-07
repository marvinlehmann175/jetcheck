// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
    // allow some public assets without auth (favicons, manifest, robots)
    const openPaths = [/^\/favicon/, /^\/apple-touch-icon\.png$/, /^\/site\.webmanifest$/, /^\/robots\.txt$/];
    if (openPaths.some((re) => re.test(req.nextUrl.pathname))) {
        const res = NextResponse.next();
        // add noindex headers anyway
        res.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive, nosnippet");
        return res;
    }

    const auth = req.headers.get("authorization");
    const user = process.env.BASIC_AUTH_USER || "jet";
    const pass = process.env.BASIC_AUTH_PASS || "check";

    // No header? Ask for creds.
    if (!auth?.startsWith("Basic ")) {
        return new NextResponse("Authentication required.", {
            status: 401,
            headers: {
                "WWW-Authenticate": 'Basic realm="Protected"',
                "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
            },
        });
    }

    // Validate header
    const [, base64] = auth.split(" ");
    const [u, p] = Buffer.from(base64, "base64").toString().split(":");

    if (u !== user || p !== pass) {
        return new NextResponse("Invalid credentials.", {
            status: 401,
            headers: {
                "WWW-Authenticate": 'Basic realm="Protected"',
                "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
            },
        });
    }

    // Add noindex headers to everything behind the gate too (belt & suspenders)
    const res = NextResponse.next();
    res.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive, nosnippet");
    return res;
}

// Protect everything
export const config = {
    matcher: ["/:path*"],
};