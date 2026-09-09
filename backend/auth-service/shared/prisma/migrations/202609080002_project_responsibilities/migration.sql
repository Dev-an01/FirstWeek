CREATE TABLE "project_responsibilities" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "status" TEXT NOT NULL DEFAULT 'ACTIVE',
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "project_responsibilities_pkey" PRIMARY KEY ("companyId", "projectId", "id"),
  CONSTRAINT "project_responsibilities_project_fkey" FOREIGN KEY ("companyId", "projectId") REFERENCES "projects"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE "responsibility_assignments" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "responsibilityId" TEXT NOT NULL,
  "ownerUserId" TEXT NOT NULL,
  CONSTRAINT "responsibility_assignments_pkey" PRIMARY KEY ("companyId", "projectId", "responsibilityId"),
  CONSTRAINT "responsibility_assignments_responsibility_fkey" FOREIGN KEY ("companyId", "projectId", "responsibilityId") REFERENCES "project_responsibilities"("companyId", "projectId", "id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "responsibility_assignments_owner_fkey" FOREIGN KEY ("companyId", "projectId", "ownerUserId") REFERENCES "project_members"("companyId", "projectId", "userId") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX "responsibility_assignments_owner_idx" ON "responsibility_assignments"("companyId", "projectId", "ownerUserId");
