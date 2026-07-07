import { Navigate, Route, Routes, NavLink, useNavigate } from "react-router-dom";
import { getToken, logout } from "./api/client";
import Dashboard from "./pages/Dashboard";
import Cameras from "./pages/Cameras";
import Alerts from "./pages/Alerts";
import Login from "./pages/Login";

function Shell({ children }: { children: React.ReactNode }) {
  const nav = useNavigate();
  const link = "px-3 py-2 rounded text-sm hover:bg-line";
  const active = ({ isActive }: { isActive: boolean }) =>
    `${link} ${isActive ? "bg-line text-amber" : "text-slate-300"}`;
  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-panel/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-6">
          <span className="font-mono text-amber tracking-tight">▣ retail-vision-ops</span>
          <nav className="flex gap-1">
            <NavLink to="/" className={active} end>Dashboard</NavLink>
            <NavLink to="/cameras" className={active}>Cameras</NavLink>
            <NavLink to="/alerts" className={active}>Alerts</NavLink>
          </nav>
          <button
            className="ml-auto text-xs text-slate-400 hover:text-slate-200"
            onClick={() => { logout(); nav("/login"); }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
    </div>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/cameras" element={<Protected><Cameras /></Protected>} />
      <Route path="/alerts" element={<Protected><Alerts /></Protected>} />
    </Routes>
  );
}
