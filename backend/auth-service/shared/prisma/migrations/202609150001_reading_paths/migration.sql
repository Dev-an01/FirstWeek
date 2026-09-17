CREATE TABLE "project_reading_steps" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "description" TEXT NOT NULL DEFAULT '',
  "documentId" TEXT NOT NULL,
  "focus" TEXT,
  "experience" TEXT,
  "position" INTEGER NOT NULL,
  "revision" INTEGER NOT NULL DEFAULT 0,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "project_reading_steps_pkey" PRIMARY KEY ("companyId", "projectId", "id"),
  CONSTRAINT "project_reading_steps_companyId_projectId_position_key" UNIQUE ("companyId", "projectId", "position"),
  CONSTRAINT "project_reading_steps_companyId_projectId_fkey" FOREIGN KEY ("companyId", "projectId") REFERENCES "projects"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "project_reading_steps_companyId_projectId_documentId_fkey" FOREIGN KEY ("companyId", "projectId", "documentId") REFERENCES "project_documents"("companyId", "projectId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX "project_reading_steps_companyId_projectId_documentId_idx" ON "project_reading_steps"("companyId", "projectId", "documentId");
CREATE TABLE "project_reading_progress" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "stepId" TEXT NOT NULL,
  "userId" TEXT NOT NULL,
  "stepRevision" INTEGER NOT NULL,
  "completedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "project_reading_progress_pkey" PRIMARY KEY ("companyId", "projectId", "stepId", "userId"),
  CONSTRAINT "project_reading_progress_companyId_projectId_userId_fkey" FOREIGN KEY ("companyId", "projectId", "userId") REFERENCES "project_members"("companyId", "projectId", "userId") ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT "project_reading_progress_companyId_projectId_stepId_fkey" FOREIGN KEY ("companyId", "projectId", "stepId") REFERENCES "project_reading_steps"("companyId", "projectId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);
CREATE INDEX "project_reading_progress_companyId_projectId_userId_idx" ON "project_reading_progress"("companyId", "projectId", "userId");
