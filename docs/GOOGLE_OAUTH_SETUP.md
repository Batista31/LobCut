# Google OAuth Setup for LobCut

1. Go to https://console.cloud.google.com/
2. Create a new project called "LobCut"
3. Go to APIs & Services -> OAuth consent screen
   - User type: External
   - App name: LobCut
   - Add scope: email, profile, openid
4. Go to APIs & Services -> Credentials
   - Create OAuth 2.0 Client ID
   - Application type: Web application
   - Authorized redirect URIs: http://localhost:8000/auth/callback
5. Copy Client ID and Client Secret to `.env`:
   ```env
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```
6. Generate JWT secret:
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   ```env
   JWT_SECRET=...
   ```
