import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/client";

export default function Login() {
  const [email, setEmail] = useState("admin@retail.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await login(email, password);
      nav("/");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center">
      <form onSubmit={submit} className="card w-80 space-y-4">
        <div>
          <div className="font-mono text-amber">▣ retail-vision-ops</div>
          <div className="text-xs text-slate-500 mt-1">Sign in to the control room</div>
        </div>
        <label className="block">
          <span className="label">Email</span>
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email"
            className="mt-1 w-full bg-ink border border-line rounded px-3 py-2 text-sm" />
        </label>
        <label className="block">
          <span className="label">Password</span>
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password"
            className="mt-1 w-full bg-ink border border-line rounded px-3 py-2 text-sm" />
        </label>
        {error && <p className="text-red-400 text-xs">{error}</p>}
        <button className="w-full bg-amber text-ink font-medium rounded py-2 text-sm">
          Sign in
        </button>
      </form>
    </div>
  );
}
