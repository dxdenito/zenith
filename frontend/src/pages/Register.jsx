import { useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase, Lock, Mail, User } from "lucide-react";
import AuthLayout from "../components/AuthLayout";
import { Button, ErrorNote, Field } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const [form, setForm] = useState({ full_name: "", workspace_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(0);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  function fail(message) {
    setError(message);
    setShake((n) => n + 1);
    setLoading(false);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (form.password.length < 8) {
      fail("Use at least 8 characters for your password.");
      return;
    }
    setLoading(true);
    try {
      await register({
        full_name: form.full_name.trim(),
        workspace_name: form.workspace_name.trim() || null,
        email: form.email.trim(),
        password: form.password,
      });
    } catch (err) {
      fail(err.message);
    }
  }

  return (
    <AuthLayout
      title="Create your space"
      subtitle="It takes a minute. Your space stays private to you."
      shake={shake}
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="text-brand">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Field
          icon={User}
          label="Your name"
          autoComplete="name"
          placeholder="Denis"
          value={form.full_name}
          onChange={set("full_name")}
          required
        />
        <Field
          icon={Briefcase}
          label="Space name (optional)"
          placeholder="My trading space"
          value={form.workspace_name}
          onChange={set("workspace_name")}
        />
        <Field
          icon={Mail}
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={form.email}
          onChange={set("email")}
          required
        />
        <Field
          icon={Lock}
          label="Password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={form.password}
          onChange={set("password")}
          required
        />
        <ErrorNote message={error} />
        <div className="pt-2">
          <Button type="submit" loading={loading}>
            Create my space
          </Button>
        </div>
      </form>
    </AuthLayout>
  );
}
