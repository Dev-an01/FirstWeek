ALTER TABLE "project_members"
  ADD COLUMN "onboardingRole" TEXT,
  ADD COLUMN "onboardingExperience" TEXT,
  ADD COLUMN "profileVersion" INTEGER NOT NULL DEFAULT 0,
  ADD CONSTRAINT "onboarding_role_allowed" CHECK ("onboardingRole" IN ('ENGINEERING', 'PRODUCT', 'DESIGN', 'OPERATIONS')),
  ADD CONSTRAINT "onboarding_experience_allowed" CHECK ("onboardingExperience" IN ('NEW', 'EXPERIENCED'));
