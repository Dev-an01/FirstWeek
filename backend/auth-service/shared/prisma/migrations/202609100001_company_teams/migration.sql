CREATE TABLE "company_teams" (
  "companyId" TEXT NOT NULL,
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "company_teams_pkey" PRIMARY KEY ("companyId", "id"),
  CONSTRAINT "company_teams_companyId_fkey" FOREIGN KEY ("companyId") REFERENCES "companies"("id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "company_teams_companyId_name_key" ON "company_teams"("companyId", "name");

CREATE TABLE "team_assignments" (
  "companyId" TEXT NOT NULL,
  "teamId" TEXT NOT NULL,
  "userId" TEXT NOT NULL,
  "assignment" TEXT NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "team_assignments_pkey" PRIMARY KEY ("companyId", "teamId", "userId"),
  CONSTRAINT "team_assignments_companyId_teamId_fkey" FOREIGN KEY ("companyId", "teamId") REFERENCES "company_teams"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "team_assignments_companyId_userId_fkey" FOREIGN KEY ("companyId", "userId") REFERENCES "users"("companyId", "id") ON DELETE CASCADE ON UPDATE RESTRICT
);
CREATE INDEX "team_assignments_companyId_userId_idx" ON "team_assignments"("companyId", "userId");
