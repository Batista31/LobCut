export function Login() {
  return (
    <main className="loginShell">
      <section className="loginCard">
        <div className="logoMark">LC</div>
        <h1>LobCut</h1>
        <p>Autonomous media processing for images, reels, and game clips.</p>
        <a className="googleButton" href="http://localhost:8000/auth/login">
          Sign in with Google
        </a>
      </section>
    </main>
  );
}
