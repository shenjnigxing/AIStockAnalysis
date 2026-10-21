import { redirect } from "next/navigation";

/** Research workspace is the primary product entrypoint in v2. */
export default function HomePage() {
  redirect("/research");
}
