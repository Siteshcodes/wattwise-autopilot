import { NextRequest, NextResponse } from "next/server";

async function proxy(request: NextRequest, context: {params: Promise<{path: string[]}>}) {
  const {path} = await context.params;
  if (path.length !== 1 || !["state", "plan", "approve"].includes(path[0])) return new NextResponse(null, {status: 404});
  // Only same-origin browser requests may mutate local simulator state.
  const incomingOrigin = `${request.nextUrl.protocol}//${request.headers.get("host")}`;
  if (request.method === "POST" && request.headers.get("origin") !== incomingOrigin) {
    return NextResponse.json({detail: {message: "Same-origin confirmation required."}}, {status: 403});
  }
  try {
    const response = await fetch(`${process.env.WATTWISE_API_URL || "http://127.0.0.1:8001"}/api/${path[0]}`, {
      method: request.method,
      headers: {"Content-Type": "application/json"},
      body: request.method === "POST" ? await request.text() : undefined,
      cache: "no-store", signal: AbortSignal.timeout(60000),
    });
    return new NextResponse(await response.text(), {status: response.status, headers: {"Content-Type": "application/json"}});
  } catch {
    return NextResponse.json({detail: {message: "Backend unavailable. Start the MCP server and dashboard gateway."}}, {status: 503});
  }
}
export const GET = proxy;
export const POST = proxy;
