// Credentials can operate only on the four isolated demonstration databases.
const demoDatabases = [
  "coyote4_demo", "coyote4_demo_identity", "coyote4_demo_knowledgebase", "coyote4_demo_bam",
];
db.getSiblingDB("admin").createUser({
  user: "coyote_demo",
  pwd: process.env.COYOTE_DEMO_MONGO_PASSWORD,
  roles: demoDatabases.flatMap((name) => [
    { role: "readWrite", db: name },
    { role: "dbAdmin", db: name },
  ]),
});
