import { getProfile } from "@/lib/auth";
import Sidebar from "@/components/Sidebar";
import SignOut from "@/components/SignOut";
import ChangePassword from "@/components/ChangePassword";
import { AppProvider } from "@/components/app";
import InstructorView from "@/components/InstructorView";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const me = await getProfile();
  if (!me?.active) {
    return (
      <div className="login">
        <div className="panel panel-b">
          <p>This account is not active. Ask the owner to activate it.</p>
          <SignOut />
        </div>
      </div>
    );
  }
  if (me.must_change_password) return <ChangePassword name={me.name} />;
  // Instructors get one screen at every address: no menu and no other pages.
  if (me.role === "instructor") return <AppProvider me={me}><InstructorView /></AppProvider>;
  return (
    <AppProvider me={me}>
      <div className="shell">
        <Sidebar me={me} />
        <main>{children}</main>
      </div>
    </AppProvider>
  );
}
