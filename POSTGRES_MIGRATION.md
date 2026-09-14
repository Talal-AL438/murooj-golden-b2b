# Murooj Golden — PostgreSQL production cutover

## Current demo
- Keep the demo service on SQLite while final acceptance testing continues.
- Take a manual SQLite backup from Super Admin before every important release.
- The temporary Render PostgreSQL instance is for migration/testing only and must not be treated as production storage.

## Production launch gate
Do not switch the public production portal until all of the following are complete:
1. Create/upgrade to a durable paid Render PostgreSQL instance.
2. Take a final SQLite backup and freeze writes during the cutover window.
3. Migrate schema and data preserving IDs and relationships.
4. Verify row counts and critical relationships for users, agencies, hotels, hotel_images, requests, offers, notifications, audit, offer_targets, staff_permissions, login_attempts, trusted_admin_devices, and pending_admin_devices.
5. Configure DATABASE_URL only on the production service.
6. Run full agency/admin acceptance tests.
7. Confirm backup/restore policy for the paid database.
8. Only then open the production URL/domain to agencies.

## Rollback
Keep the final SQLite backup unchanged until production PostgreSQL has passed acceptance testing. If cutover validation fails, do not accept new production writes; restore the previous release/data and investigate before retrying.

## Important
The application currently contains SQLite-specific schema/migration SQL (including PRAGMA/sqlite_master/AUTOINCREMENT). Installing the PostgreSQL driver alone does not make the app PostgreSQL-compatible. Database abstraction and migration code must be completed and tested before DATABASE_URL is enabled.
