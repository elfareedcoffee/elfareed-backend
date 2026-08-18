# Production Smoke Test Checklist

Execute this smoke test immediately following a production deployment to verify system stability and core functionality. **Do not perform destructive tests against production data.** 

## 1. System Health
- [ ] **API Starts:** The Docker container is running without restart loops.
- [ ] **Liveness Check:** `GET /api/v1/health` returns `{"status": "ok"}`.
- [ ] **Readiness Check:** `GET /api/v1/health/ready` returns `{"status": "ready"}`.
- [ ] **Database Connection:** Confirmed via Readiness Check. No errors in startup logs.

## 2. Public Catalog
- [ ] **Public Categories:** `GET /api/v1/public/categories` returns a 200 response with active categories.
- [ ] **Public Products:** `GET /api/v1/public/products` returns a 200 response. Only active products should be visible.
- [ ] **Localization:** Passing `Accept-Language: ar` returns content in Arabic. Passing `Accept-Language: en` returns content in English.

## 3. Order & Cart Flow (Non-Destructive)
- [ ] **Guest Cart:** A `POST` to `/api/v1/public/cart/items` with a valid variant ID correctly creates a cart and returns an `x-cart-id` header.
- [ ] **Checkout Validation:** Submit a checkout request with clearly invalid phone numbers or missing fields to confirm validation errors are returned with standard error structures.
- [ ] **Order Tracking:** Use an existing, known test `tracking_number` to hit `GET /api/v1/public/orders/track/{tracking_number}`. Verify it returns 200 without exposing sensitive payment info.
- [ ] **Order Recovery:** Hit `POST /api/v1/public/orders/recover` with an existing customer phone number to verify the recovery SMS flow is triggered (if integrated).

## 4. Admin Functionality
- [ ] **Admin Authentication:** Authenticate as an Admin user to receive a JWT. Verify invalid passwords return a standard 401.
- [ ] **Admin Orders:** `GET /api/v1/admin/orders` returns a paginated list of orders (requires Auth token).
- [ ] **Dashboard Statistics:** `GET /api/v1/admin/dashboard/statistics` returns numerical statistics without 500 errors.
- [ ] **Image Upload (Verification only):** Attempt an upload with an invalid file format (e.g. PDF) to `POST /api/v1/admin/products/{id}/image`. Verify it is rejected with a 400 Bad Request to ensure storage security rules are enforced.

## 5. Security & Error Handling
- [ ] **Error Structure:** Ensure 404s (e.g., fetching a non-existent URL) and 401s (accessing admin without token) return standardized JSON responses.
- [ ] **CORS Verification:** Send an `OPTIONS` request with an Origin header not in `ALLOWED_ORIGINS` to ensure it is blocked.
- [ ] **No Stack Traces:** Force a 500 or 400 error and verify the response body does not leak server stack traces.
