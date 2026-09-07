// backend/auth-service/config/database.js

const path = require("path");

// Load environment variables
require("dotenv").config({
  path: path.resolve(__dirname, "../../../.env"),
});

// eslint-disable-next-line
const {
  prisma,
  connectDatabase,
  healthCheck,
  // eslint-disable-next-line
} = require('../shared/lib/databaseUtils');

let isConnected = false;

const initializeDatabase = async () => {
  if (isConnected) {
    return prisma;
  }

  try {
    // Test connection
    await connectDatabase();
    isConnected = true;

    console.log("✅ Database service initialized");
    return prisma;
  } catch (error) {
    console.error("❌ Database initialization failed:", error.message);
    throw error;
  }
};

const getDatabase = async () => {
  if (!isConnected) {
    await initializeDatabase();
  }
  return prisma;
};

const disconnectDatabase = async () => {
  if (prisma) {
    await prisma.$disconnect();
    isConnected = false;
    console.log("📤 Database disconnected");
  }
};

module.exports = {
  initializeDatabase,
  getDatabase,
  disconnectDatabase,
  healthCheck,
};
