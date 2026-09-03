/* Initialize the per-database app user for the repository-managed Docker Mongo instance.
 * Runs only on first initialization of an empty /data/db volume.
 */
const appDbName = process.env.COYOTE3_DB;
const knowledgebaseDbName = process.env.KNOWLEDGEBASE_DB;
const bamDbName = process.env.BAM_DB;
const appUser = process.env.MONGO_APP_USER;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appDbName || !knowledgebaseDbName || !bamDbName) {
  throw new Error("COYOTE3_DB, KNOWLEDGEBASE_DB, and BAM_DB must be configured explicitly");
}

if (knowledgebaseDbName === appDbName || knowledgebaseDbName === bamDbName) {
  throw new Error("KNOWLEDGEBASE_DB must be different from COYOTE3_DB and BAM_DB");
}

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
        { role: "readWrite", db: knowledgebaseDbName },
        { role: "readWrite", db: bamDbName },
      ],
    });
    print(
      `[mongo-init] created app user '${appUser}' with application, knowledgebase, and BAM access`
    );
  }
}
