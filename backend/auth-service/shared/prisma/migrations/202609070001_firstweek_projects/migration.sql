-- Additive FirstWeek membership schema. No existing data is changed.
CREATE UNIQUE INDEX "users_companyId_id_key" ON "users"("companyId", "id");

CREATE TABLE "projects" (
  "id" TEXT NOT NULL,
  "companyId" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "isActive" BOOLEAN NOT NULL DEFAULT true,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "projects_pkey" PRIMARY KEY ("companyId", "id"),
  CONSTRAINT "projects_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE TABLE "project_members" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "userId" TEXT NOT NULL,
  "role" TEXT NOT NULL DEFAULT 'MEMBER',
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "project_members_pkey" PRIMARY KEY ("companyId", "projectId", "userId"),
  CONSTRAINT "project_members_companyId_projectId_fkey" FOREIGN KEY ("companyId", "projectId") REFERENCES "projects"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "project_members_companyId_userId_fkey" FOREIGN KEY ("companyId", "userId") REFERENCES "users"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX "project_members_userId_idx" ON "project_members"("userId");
