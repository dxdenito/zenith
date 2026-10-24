import { Navigate, Route, Routes } from "react-router-dom";
import { motion } from "motion/react";
import { useAuth } from "./context/AuthContext";
import AppShell from "./components/AppShell";
import Brand from "./components/Brand";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Home from "./pages/Home";
import Placeholder from "./pages/Placeholder";
import Settings from "./pages/Settings";
import Markets from "./pages/Markets";

function Splash() {
  return (
    <div className="grid min-h-dvh place-items-center">
      <motion.div
        animate={{ scale: [1, 1.08, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
      >
        <Brand />
      </motion.div>
    </div>
  );
}

function Protected() {
  const { user, loading } = useAuth();
  if (loading) return <Splash />;
  return user ? <AppShell /> : <Navigate to="/login" replace />;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Splash />;
  return user ? <Navigate to="/" replace /> : children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
      <Route element={<Protected />}>
        <Route index element={<Home />} />
        <Route path="markets" element={<Markets />} />
        <Route path="analysis" element={<Placeholder />} />
        <Route path="trade" element={<Placeholder />} />
        <Route path="settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
