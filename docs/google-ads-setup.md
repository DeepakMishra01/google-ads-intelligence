# Google Ads API configuration guide

To sync data you need four credentials tied to your **Manager (MCC) account**:

1. **Developer token**
2. **OAuth client id + secret**
3. **OAuth refresh token**
4. **Login customer id** (the MCC id)

## 1. Developer token

1. Sign in to your **MCC** account at <https://ads.google.com>.
2. Go to **Tools & Settings → Setup → API Center**.
3. Apply for / copy the **developer token**.
   - New tokens start with **Test account** access. Apply for **Basic access**
     to query production accounts.

## 2. OAuth client (Google Cloud)

1. In <https://console.cloud.google.com>, create/select a project.
2. **APIs & Services → Enable APIs → enable "Google Ads API".**
3. **APIs & Services → Credentials → Create credentials → OAuth client ID.**
   - Application type: **Desktop app** (simplest for a server-side refresh token)
     or **Web** if you already run an OAuth redirect.
4. Note the **client id** and **client secret**.
5. Configure the OAuth consent screen; add your user as a test user if the app is
   in "Testing".

## 3. Refresh token

Use Google's helper to generate a long-lived refresh token for the MCC login
user. With the `google-ads` library installed:

```bash
# Fill client id/secret when prompted; scope is https://www.googleapis.com/auth/adwords
python -m google.ads.googleads.util.generate_user_credentials \
    --client_id=YOUR_CLIENT_ID --client_secret=YOUR_CLIENT_SECRET
```

(or the script at
<https://developers.google.com/google-ads/api/docs/oauth/cloud-project>).
Copy the printed **refresh token**.

> The user that authorizes must have access to the MCC so the token can reach all
> child accounts.

## 4. Login customer id

This is your **MCC account id** with dashes removed (e.g. `123-456-7890` →
`1234567890`). It is sent as `login-customer-id` on every request so the API
resolves the account hierarchy.

## 5. Put it together

In `.env`:

```
GOOGLE_ADS_DEVELOPER_TOKEN=xxxxxxxxxxxxxxxxxxxxxx
GOOGLE_ADS_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_ADS_CLIENT_SECRET=xxxxxxxxxxxxxxxx
GOOGLE_ADS_REFRESH_TOKEN=1//xxxxxxxxxxxxxxxx
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

Alternatively, place a `google-ads.yaml` somewhere and set
`GOOGLE_ADS_YAML_PATH=/path/to/google-ads.yaml`; it overrides the discrete vars.

## 6. Verify

```bash
curl -X POST "http://localhost:8000/api/v1/sync?run_in_background=false" \
     -H "Content-Type: application/json" -d '{"entity": "accounts"}'
```

This runs account discovery only. A `success` status and populated `/accounts`
means credentials are working. Then run `{"entity": "all"}` for a full sync.

## How the platform uses these

- The client is built lazily from these values in
  `app/google_ads/client.py` (`GoogleAdsClientFactory`).
- `login_customer_id` is set on the client; per-account queries pass each child
  `customer_id` explicitly.
- Account discovery queries `customer_client` under the MCC to enumerate child
  accounts (`app/google_ads/reports/accounts.py`).

## Common issues

| Error | Cause / fix |
|---|---|
| `DEVELOPER_TOKEN_NOT_APPROVED` | Token still Test-access; apply for Basic |
| `USER_PERMISSION_DENIED` | Authorizing user lacks access to that customer |
| `AUTHENTICATION_ERROR` | Bad/expired refresh token or client secret |
| `CUSTOMER_NOT_ENABLED` | Child account is cancelled/suspended |
| Quota / `RESOURCE_EXHAUSTED` | Handled automatically with backoff + retry |
