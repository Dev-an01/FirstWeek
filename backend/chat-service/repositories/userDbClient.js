// backend/chat-service/repositories/userDbClient.js
// Prisma client for accessing user data from auth database (avatar_user_db)

const { PrismaClient } = require("../shared/lib/generated/authClient");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("user-db-client");

// Create Prisma client pointing to avatar_user_db (auth database)
// Override DATABASE_URL environment variable before creating client
const authDbUrl =
  process.env.AUTH_DATABASE_URL ||
  "postgresql://postgres:postgres123@avatar-user-db:5432/avatar_user_db";

const userDb = new PrismaClient({
  datasources: {
    db: {
      url: authDbUrl,
    },
  },
});

logger.info(
  "UserDB client initialized for auth database:",
  authDbUrl.replace(/:[^:@]+@/, ":***@"),
);

module.exports = userDb;
