// auth-service/repositories/emailRepository.js
const { getDatabase } = require("../config/database");
const {
  transformError,
  ValidationError,
  NotFoundError,
  // eslint-disable-next-line
} = require('../shared/utils/errors');

let dbInstance = null;

const getDB = async () => {
  if (!dbInstance) {
    dbInstance = await getDatabase();
  }
  return dbInstance;
};

/**
 * Create or update email verification record
 */
const createOrUpdateVerification = async (verificationData) => {
  try {
    const db = await getDB();

    // Delete existing unverified record for this email
    await db.emailVerification.deleteMany({
      where: {
        email: verificationData.email,
        isVerified: false,
      },
    });

    // Create new verification record
    const newRecord = await db.emailVerification.create({
      data: verificationData,
      select: {
        id: true,
        userId: true,
        email: true,
        expiresAt: true,
        attempts: true,
        isVerified: true,
        createdAt: true,
      },
    });

    return newRecord;
  } catch (error) {
    throw transformError(error, "createOrUpdateVerification");
  }
};

/**
 * Find verification record by email
 */
const findVerificationByEmail = async (email) => {
  try {
    const db = await getDB();

    const record = await db.emailVerification.findFirst({
      where: {
        email: email,
        isVerified: false,
        expiresAt: { gt: new Date() },
      },
      select: {
        id: true,
        userId: true,
        email: true,
        otp: true,
        token: true,
        expiresAt: true,
        attempts: true,
        isVerified: true,
        createdAt: true,
      },
    });

    return record;
  } catch (error) {
    throw transformError(error, "findVerificationByEmail");
  }
};

/**
 * Verify OTP and mark as verified
 */
const verifyOtp = async (email, otp) => {
  try {
    const db = await getDB();

    // Find active verification record
    const record = await db.emailVerification.findFirst({
      where: {
        email: email,
        isVerified: false,
        expiresAt: { gt: new Date() },
      },
    });

    if (!record) {
      throw NotFoundError("No active verification found for this email");
    }

    // Check if too many attempts
    if (record.attempts >= 5) {
      throw ValidationError(
        "Too many verification attempts. Please request a new OTP.",
      );
    }

    // Check if OTP matches
    if (record.otp !== otp) {
      // Increment attempts
      await db.emailVerification.update({
        where: { id: record.id },
        data: { attempts: record.attempts + 1 },
      });
      throw ValidationError("Invalid OTP provided");
    }

    // Mark as verified
    const verifiedRecord = await db.emailVerification.update({
      where: { id: record.id },
      data: {
        isVerified: true,
        attempts: record.attempts + 1,
      },
      select: {
        id: true,
        userId: true,
        email: true,
        isVerified: true,
      },
    });

    return verifiedRecord;
  } catch (error) {
    throw transformError(error, "verifyOtp");
  }
};

/**
 * Check verification status
 */
const getVerificationStatus = async (email) => {
  try {
    const db = await getDB();

    const record = await db.emailVerification.findFirst({
      where: { email: email },
      select: {
        attempts: true,
        expiresAt: true,
        isVerified: true,
        createdAt: true,
      },
      orderBy: { createdAt: "desc" },
    });

    if (!record) {
      return {
        attempts: 0,
        canRetry: true,
        expiresAt: null,
        isVerified: false,
      };
    }

    const isExpired = record.expiresAt < new Date();
    const canRetry = record.attempts < 100 && !isExpired && !record.isVerified;

    return {
      attempts: record.attempts,
      canRetry,
      expiresAt: record.expiresAt,
      isExpired,
      isVerified: record.isVerified,
    };
  } catch (error) {
    throw transformError(error, "getVerificationStatus");
  }
};

/**
 * Clean up expired verification records
 */
const cleanupExpiredVerifications = async () => {
  try {
    const db = await getDB();

    const deletedRecords = await db.emailVerification.deleteMany({
      where: {
        expiresAt: { lt: new Date() },
        isVerified: false,
      },
    });

    return { deletedCount: deletedRecords.count };
  } catch (error) {
    throw transformError(error, "cleanupExpiredVerifications");
  }
};

module.exports = {
  createOrUpdateVerification,
  findVerificationByEmail,
  verifyOtp,
  getVerificationStatus,
  cleanupExpiredVerifications,
};
