import { useEffect, useRef } from "react";

// Set VITE_GOOGLE_CLIENT_ID (Vercel + local .env) to the OAuth Web Client ID.
// When it is empty the button renders nothing, so the app still works without
// Google configured.
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
const GSI_SRC = "https://accounts.google.com/gsi/client?hl=en";

export default function GoogleSignInButton({ onCredential, text = "signin_with" }) {
  const ref = useRef(null);
  const cbRef = useRef(onCredential);
  cbRef.current = onCredential;

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;

    function render() {
      if (cancelled || !window.google?.accounts?.id || !ref.current) return;
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        locale: "en",
        callback: (resp) => { if (resp?.credential) cbRef.current?.(resp.credential); },
      });
      ref.current.innerHTML = "";
      window.google.accounts.id.renderButton(ref.current, {
        theme: "outline", size: "large", text, shape: "pill",
        logo_alignment: "center", width: 320,
      });
    }

    if (window.google?.accounts?.id) {
      render();
    } else {
      let s = document.getElementById("gsi-script");
      if (!s) {
        s = document.createElement("script");
        s.src = GSI_SRC; s.async = true; s.defer = true; s.id = "gsi-script";
        document.head.appendChild(s);
      }
      s.addEventListener("load", render);
    }
    return () => { cancelled = true; };
  }, [text]);

  if (!CLIENT_ID) return null;
  return <div className="gsi-btn-wrap" ref={ref} />;
}
