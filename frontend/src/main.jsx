import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { MotionConfig } from "motion/react";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import "./index.css";
import { AccountProvider } from "./context/AccountContext";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>          
            <AccountProvider>
              <App />
            </AccountProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </MotionConfig>
  </StrictMode>
);
