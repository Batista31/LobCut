export function Login() {
  return (
    <main className="loginShell">
      <section className="loginCard">
        <img className="loginLogo" src="logo-white.jpeg" alt="LobCut" />
        <p className="loginTagline">Autonomous Media Processing Agent</p>
        <p>Process images, reels, and game clips — zero human intervention.</p>
        <a className="googleButton" href="http://localhost:8000/auth/login">
          Sign in with Google
        </a>
      </section>
    </main>
  );
}
