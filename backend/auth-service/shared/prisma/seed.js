// backend/auth-service/shared/prisma/seed.js
const bcrypt = require("bcryptjs");
const { PrismaClient } = require("../lib/generated/client");

const prisma = new PrismaClient();

async function main() {
  console.log("🌱 Starting database seeding...");

  // =========================================================
  // SUPER_ADMIN account - the first admin user
  // =========================================================
  const superAdmin = {
    username: "cap2k4",
    email: "cap2k4@gmail.com",
    firstName: "Akshay",
    lastName: "Behl",
    password: process.env.SEED_ADMIN_PASSWORD || "AkshayBehl2004",
    role: "SUPER_ADMIN",
    emailVerified: true,
    isActive: true,
    isCompanyVerified: true, // SUPER_ADMIN doesn't need company verification
  };

  try {
    // =========================================================
    // Create SUPER_ADMIN user if not exists
    // =========================================================
    const existingAdmin = await prisma.user.findFirst({
      where: {
        OR: [
          { email: superAdmin.email },
          { username: superAdmin.username },
        ],
      },
    });

    if (existingAdmin) {
      console.log("⚠️  Super Admin user already exists. Checking role...");
      console.log(`   Username: ${existingAdmin.username}`);
      console.log(`   Email: ${existingAdmin.email}`);
      console.log(`   Role: ${existingAdmin.role}`);

      // Ensure existing admin has SUPER_ADMIN role
      // And update password to ensure we can login
      const hashedPassword = await bcrypt.hash(superAdmin.password, 10);
      await prisma.user.update({
        where: { id: existingAdmin.id },
        data: {
          role: "SUPER_ADMIN",
          isCompanyVerified: true,
          password: hashedPassword
        }
      });
      console.log(`   ✓ Updated role to SUPER_ADMIN and reset password`);
      return;
    }

    // Hash the password
    const hashedPassword = await bcrypt.hash(superAdmin.password, 10);

    // Create the super admin user
    const admin = await prisma.user.create({
      data: {
        username: superAdmin.username,
        email: superAdmin.email,
        firstName: superAdmin.firstName,
        lastName: superAdmin.lastName,
        password: hashedPassword,
        role: superAdmin.role,
        emailVerified: superAdmin.emailVerified,
        emailVerifiedAt: new Date(),
        isActive: superAdmin.isActive,
        isCompanyVerified: superAdmin.isCompanyVerified,
        // SUPER_ADMIN doesn't belong to a company - they manage all companies
        companyId: null,
      },
    });

    console.log("✅ Super Admin user created successfully!");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("🔐 SUPER ADMIN CREDENTIALS (CHANGE IMMEDIATELY!)");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log(`   Username: ${superAdmin.username}`);
    console.log(`   Email: ${superAdmin.email}`);
    console.log(`   Role: ${admin.role}`);
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    console.log("⚠️  SECURITY WARNING:");
    console.log("   1. Change the admin password immediately after first login");
    console.log("   2. Use a strong, unique password");
    console.log("   3. Never commit credentials to version control");
    console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  } catch (error) {
    console.error("❌ Error in seed script:", error);
    throw error;
  }
}

main()
  .catch((error) => {
    console.error("💥 Seed script failed:", error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
    console.log("🌱 Database seeding completed");
  });
