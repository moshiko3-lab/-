import { redirect } from "next/navigation";
import SettingsView from "@/components/SettingsView";
import { getProfile } from "@/lib/auth";
import { googleReady } from "@/lib/google";

export default async function SettingsPage() {
  if ((await getProfile())?.role !== "owner") redirect("/");
  return <SettingsView googleReady={googleReady()} />;
}
