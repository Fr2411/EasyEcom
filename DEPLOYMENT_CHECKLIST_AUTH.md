# Auth rollout checklist (production)

1. **Pre-flight backup**
   - Backup `users` and `user_roles` tables.
2. **Apply migration**
   - Run `easy_ecom/migrations/20260309_add_users_password_hash.sql`.
3. **Set environment variables**
   - `SESSION_SECRET` (strong random)
   - `SESSION_COOKIE_SECURE=true`
   - `SESSION_COOKIE_DOMAIN=easy-ecom.online`
   - `SESSION_COOKIE_SAMESITE=lax`
4. **Bootstrap super admin safely**
   - Reset super admin password using hashed password flow (create/update user through app admin path).
5. **Deploy backend**
   - Deploy API service and verify `/health` and `/auth/me` behavior.
6. **Deploy frontend**
   - Ensure `NEXT_PUBLIC_API_BASE_URL` points to backend HTTPS origin.
7. **Validation**
   - Login with an existing plaintext-password account once and verify `password_hash` is populated and `password` is blank.
   - Verify anonymous users are redirected to `/login`.
8. **Post-deploy hardening**
   - Rotate temporary admin passwords.
   - Monitor failed login counts and 401 spikes.
