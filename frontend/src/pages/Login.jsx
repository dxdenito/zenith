import { useState } from "react";
import { Link } from "react-router-dom";
import { Lock, Mail } from "lucide-react";
import AuthLayout from "../components/AuthLayout";
import { Button, ErrorNote, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(0);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setError(err.message);
      setShake((n) => n + 1);
      setLoading(false);
    }
  }

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to pick up where you left off."
      shake={shake}
      footer={
        <>
          New here?{" "}
          <Link to="/register" className="text-brand">
            Create your space
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Field
          icon={Mail}
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Field
          icon={Lock}
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <ErrorNote message={error} />
        <div className="pt-2">
          <Button type="submit" loading={loading}>
            Sign in
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
}
