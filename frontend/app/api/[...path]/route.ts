import { NextRequest } from 'next/server'

const FASTAPI_URL = process.env.API_BASE_URL ?? 'http://localhost:8000'

async function handler(request: NextRequest) {
  const pathname = request.nextUrl.pathname.replace(/^\/api/, '') || '/'
  const url = `${FASTAPI_URL}${pathname}${request.nextUrl.search}`

  const forwardHeaders = new Headers()
  for (const [key, value] of request.headers.entries()) {
    if (!['host', 'connection', 'transfer-encoding'].includes(key.toLowerCase())) {
      forwardHeaders.set(key, value)
    }
  }

  const body =
    request.method !== 'GET' && request.method !== 'HEAD'
      ? await request.arrayBuffer()
      : undefined

  const upstream = await fetch(url, {
    method: request.method,
    headers: forwardHeaders,
    body,
  })

  const responseHeaders = new Headers()
  for (const [key, value] of upstream.headers.entries()) {
    if (!['transfer-encoding', 'connection'].includes(key.toLowerCase())) {
      responseHeaders.set(key, value)
    }
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}

export const GET = handler
export const POST = handler
export const PUT = handler
export const PATCH = handler
export const DELETE = handler
