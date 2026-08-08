import { NextResponse } from "next/server";

import { API_V1 } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Resume download proxy.
 *
 * A plain <a href> from the browser carries no Authorization header, so it
 * cannot hit the API directly. This handler attaches the token server-side,
 * then hands the browser whatever the API replies with:
 *
 *   - S3/MinIO  -> a 302 to a short-lived presigned URL, so the file bytes
 *                  never pass through Next at all.
 *   - local disk -> a stream, piped straight through.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const token = await getSessionToken();

  if (!token) {
    return NextResponse.redirect(new URL("/admin/login", _request.url));
  }

  const response = await fetch(`${API_V1}/leads/${id}/resume`, {
    headers: { Authorization: `Bearer ${token}` },
    // Handle the redirect ourselves so the presigned URL reaches the browser
    // instead of being followed server-side.
    redirect: "manual",
    cache: "no-store",
  });

  const location = response.headers.get("location");
  if (location) {
    return NextResponse.redirect(location);
  }

  if (!response.ok || !response.body) {
    return NextResponse.json(
      { error: { code: "download_failed", message: "Could not download the resume." } },
      { status: response.status === 404 ? 404 : 502 },
    );
  }

  return new NextResponse(response.body, {
    status: 200,
    headers: {
      "Content-Type":
        response.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition":
        response.headers.get("content-disposition") ?? "attachment",
    },
  });
}
