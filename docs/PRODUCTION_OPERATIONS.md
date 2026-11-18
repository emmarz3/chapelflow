# Production operations

This runbook covers the production resources defined in `render.yaml`, encrypted
PostgreSQL backups, release/rollback, alerting, and the provider checks required
before launch. Keep provider credentials in Render/GitHub secret stores; do not
put real credentials in this repository.

## Deploy the production stack

The Render Blueprint provisions the Django API, PostgreSQL, persistent Redis
Key Value, a Celery worker, and one Celery Beat scheduler. The web service runs
database migrations and bootstrap commands at startup. Review costs and data
region with the project owner before syncing the Blueprint.

1. Create/sync the Blueprint from the production branch.
2. Configure the `sync: false` API secrets in Render. Set exact values for
   `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, email, Cloudinary, and any
   payment, SMS, push, S3, or Supabase provider approved for launch.
3. Configure the frontend build for API mode and make its `/api` rewrite target
   the deployed API. Set the deployed frontend origin in the API CORS and CSRF
   allowlists.
4. Confirm the `chapelflow-celery-worker` and `chapelflow-celery-beat` services
   are healthy. Keep exactly one Beat instance to avoid duplicate schedules.
5. Run the health, login, account provisioning, upload, queued task, email, and
   payment sandbox smoke checks after each release.

Do not enable a provider until its secrets and callback/webhook URLs are
configured and a success and failure path has been exercised. SMS and FCM code
currently reports stubbed delivery when credentials are absent.

## Encrypted PostgreSQL backups

`.github/workflows/postgres-backup.yml` runs a custom-format `pg_dump` daily,
encrypts it with `age`, and uploads it to a private S3 bucket using GitHub OIDC.
Before enabling it:

- Add GitHub Actions secret `PRODUCTION_DATABASE_URL` (read-only database
  credentials are preferred for backups).
- Add GitHub Actions secret `BACKUP_AGE_RECIPIENT` containing the public age
  recipient. Store the matching private identity offline in approved custody;
  it must not be added to GitHub or Render.
- Add GitHub Actions secret `BACKUP_AWS_ROLE_ARN` and repository variables
  `BACKUP_AWS_REGION` and `BACKUP_S3_BUCKET`.
- Configure the AWS role trust policy for this repository/workflow using GitHub
  OIDC. Grant only `s3:PutObject` to the backup prefix. Keep the bucket private,
  enable versioning, and apply a lifecycle retention period approved by
  Chrisland's data owner.
- Enable workflow failure notifications for the maintainers responsible for
  the database. Confirm the first object appears in S3 and the run is green.

### Restore drill

Run at least once before launch and on the approved recurring schedule:

1. Create a separate, isolated PostgreSQL restore database. Never use the
   production database for a drill.
2. Download one encrypted object from the backup prefix and decrypt it using
   the offline age identity, piping directly into `pg_restore`:

   ```sh
   aws s3 cp s3://BUCKET/chapelflow/postgres/BACKUP.dump.age - \
     | age --decrypt --identity /secure/offline/age-identity.txt \
     | pg_restore --exit-on-error --no-owner --no-acl --dbname="$RESTORE_DATABASE_URL"
   ```

3. Start the API against the restored database in an isolated environment and
   verify migration state, representative account/attendance/report rows,
   storage references, and a login smoke check.
4. Record backup timestamp, restore duration, row/smoke-check outcome, operator,
   and any corrective action. Delete the isolated database when approved.

The Chrisland data owner must set and approve recovery-point and recovery-time
objectives (RPO/RTO) before calling the backup process production-ready.

## Release, rollback, and alerting

- Deploy a reviewed commit to a staging environment first. Run migrations,
  Django deploy checks, API/frontend journeys, and a queued task through the
  worker before promoting it.
- Before schema changes, confirm a usable backup. Prefer backward-compatible
  expand/migrate/contract changes. Do not roll application code back across an
  irreversible migration without the database owner's recovery decision.
- For rollback, redeploy the last known-good application revision, verify
  `/health/`, login, a representative read/write journey, and queue processing.
  Restore data only under the incident lead's approval.
- Configure alerts in the hosting/monitoring accounts for API health and error
  rate, worker/Beat health, Redis availability/pressure, database storage and
  connection saturation, provider delivery failures, and backup workflow
  failures. Route them to named on-call/support contacts and test each alert.
- Preserve access-controlled logs and incident records according to the
  retention schedule approved by Chrisland.

## Provider launch checks

For each provider actually enabled, record owner, environment, callback URL,
credentials location, sandbox/live test date, successful delivery/result,
failure behavior, and support contact. Required integration families are
PostgreSQL, Redis/Celery, object storage, SMTP, Paystack or Flutterwave, Termii,
FCM, maps, livestream, and approved upload malware scanning. A provider that
is not approved or configured stays disabled and must not be described as live.
