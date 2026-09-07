// backend/admin-module/shared/lib/databaseUtils.js

const { prisma } = require("./prisma");
/**
 * Test database connection
 * @returns {Promise<boolean>}
 */
async function connectDatabase() {
  try {
    await prisma.$connect();
    console.log("✅ Database connected successfully");
    return true;
  } catch (error) {
    console.error("❌ Database connection failed:", error.message);
    return false;
  }
}

/**
 * Disconnect from database
 * @returns {Promise<void>}
 */
async function disconnectDatabase() {
  try {
    await prisma.$disconnect();
    console.log("📤 Database disconnected");
  } catch (error) {
    console.error("❌ Database disconnect failed:", error.message);
  }
}
/**
 * Health check for database
 * @returns {Promise<object>}
 */
async function healthCheck() {
  try {
    const start = Date.now();
    await prisma.$queryRaw`SELECT 1`;
    const duration = Date.now() - start;

    return {
      status: "healthy",
      database: "postgresql",
      responseTime: `${duration}ms`,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    return {
      status: "unhealthy",
      database: "postgresql",
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  }
}
module.exports = {
  prisma,
  connectDatabase,
  disconnectDatabase,
  healthCheck,
};
