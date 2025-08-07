// frontend/middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// lock everything except Next internals & public assets
export const config = {
  matcher: [
    '/((?!_next/|favicon|apple-touch-icon|site\\.webmanifest|robots\\.txt).*)',
  ],
};

export function middleware(req: NextRequest) {
  const user = process.env.BASIC_AUTH_USER || '';
  const pass = process.env.BASIC_AUTH_PASS || '';

  // If creds not set in env, do nothing (no lock in preview/local)
  if (!user || !pass) return NextResponse.next();

  const authorization = req.headers.get('authorization');

  // Ask for credentials
  if (!authorization?.startsWith('Basic ')) {
    return new Response('Auth required', {
      status: 401,
      headers: { 'WWW-Authenticate': 'Basic realm="JetCheck"' },
    });
  }

  try {
    const b64 = authorization.split(' ')[1] || '';
    // Edge-safe decode: atob + TextDecoder
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const decoded = new TextDecoder().decode(bytes);
    const [u, p] = decoded.split(':');

    if (u === user && p === pass) {
      return NextResponse.next();
    }
  } catch {
    // fallthrough to unauthorized
  }

  return new Response('Unauthorized', {
    status: 401,
    headers: { 'WWW-Authenticate': 'Basic realm="JetCheck"' },
  });
}