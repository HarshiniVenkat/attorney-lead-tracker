import { redirect } from "next/navigation";

/** The root is the public form; the internal UI lives under /admin. */
export default function HomePage() {
  redirect("/apply");
}
