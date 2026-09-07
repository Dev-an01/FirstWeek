// backend/auth-service/shared/lib/prisma-main.js
// CommonJS version of Prisma client

const path = require("path");
const { PrismaClient } = require("./generated/client");

// Load environment variables
require("dotenv").config({
  path: path.resolve(__dirname, "../../../../.env"),
});

const globalForPrisma = globalThis;

const prisma =
  globalForPrisma.prisma ||
  new PrismaClient({
    log:
      process.env.NODE_ENV === "development"
        ? ["query", "error", "warn"]
        : ["error"],
    datasources: {
      db: {
        url: process.env.DATABASE_URL,
      },
    },
  });

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

// Graceful shutdown
process.on("beforeExit", async () => {
  await prisma.$disconnect();
});

module.exports = { prisma };
