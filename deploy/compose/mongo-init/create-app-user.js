/* Initialize per-database app user for compose-managed Mongo instances.
 * Runs only on first initialization of an empty /data/db volume.
 */
const appDbName = process.env.COYOTE3_DB || "coyote3";
const bamDbName = process.env.BAM_DB || "BAM_Service";
const appUser = process.env.MONGO_APP_USER;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPassword) {
  print("[mongo-init] MONGO_APP_USER or MONGO_APP_PASSWORD is missing; skipping app user creation");
} else {
  const appDb = db.getSiblingDB(appDbName);
  const existing = appDb.getUser(appUser);
  if (existing) {
    print(`[mongo-init] user '${appUser}' already exists in db '${appDbName}'`);
  } else {
    appDb.createUser({
      user: appUser,
      pwd: appPassword,
      roles: [
        { role: "readWrite", db: appDbName },
        { role: "readWrite", db: bamDbName },
      ],
    });
    print(
      `[mongo-init] created app user '${appUser}' in db '${appDbName}' with readWrite on '${bamDbName}'`
    );
  }
}
